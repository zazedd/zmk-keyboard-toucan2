{
  pkgs,
  lib,
  buildEnvironment,
}:
let
  projects = lib.importJSON ./west-sources.json;
  manifest = pkgs.writeText "west.yml" (
    builtins.toJSON {
      manifest = {
        projects = map (project: removeAttrs project [ "hash" ]) projects;
        self.path = "manifest";
      };
    }
  );
  sources = map (
    project:
    let
      repository = lib.splitString "/" (lib.removePrefix "https://github.com/" project.url);
    in
    project
    // {
      source = pkgs.fetchFromGitHub {
        owner = builtins.elemAt repository 0;
        repo = builtins.elemAt repository 1;
        rev = project.revision;
        inherit (project) hash;
      };
    }
  ) projects;

  # The resolved manifest has no imports and needs no Git metadata or network.
  workspace = pkgs.runCommand "toucan-west-workspace" { } ''
    mkdir -p "$out/manifest" "$out/.west"
    cp ${manifest} "$out/manifest/west.yml"
    printf '[manifest]\npath = manifest\nfile = west.yml\n' > "$out/.west/config"
    ${lib.concatMapStringsSep "\n" (project: ''
      mkdir -p "$out/$(dirname ${lib.escapeShellArg project.path})"
      ln -s ${project.source} "$out/${project.path}"
    '') sources}
  '';

  src = lib.fileset.toSource {
    root = ../.;
    fileset = lib.fileset.unions [
      ../boards
      ../config
      ../zephyr
    ];
  };

  mkFirmware =
    side:
    let
      isLeft = side == "left";
      shields = "toucan_${side} rgbled_adapter" + lib.optionalString isLeft " nice_view_gem";
    in
    pkgs.stdenvNoCC.mkDerivation {
      pname = "toucan-${side}";
      version = "0.3";
      inherit src;
      nativeBuildInputs = buildEnvironment.packages;
      env = buildEnvironment.env;
      dontConfigure = true;
      dontFixup = true;

      buildPhase = ''
        runHook preBuild
        configRoot="$PWD"
        export HOME="$TMPDIR"
        mkdir "$TMPDIR/west"
        cp -R --no-preserve=mode ${workspace}/. "$TMPDIR/west/"
        cd "$TMPDIR/west"

        # Zephyr's CMake library names require consistent, non-symlinked paths.
        for project in ${lib.escapeShellArgs (map (project: project.path) projects)}; do
          projectSource=$(readlink "$project")
          rm "$project"
          cp -R --no-preserve=mode "$projectSource" "$project"
        done

        # nanopb generates Python modules and needs host-native shebangs.
        patch -p1 -d modules/lib/nanopb < ${../patches/nanopb-importlib-resources.patch}
        chmod +x modules/lib/nanopb/generator/{nanopb_generator,protoc,protoc-gen-nanopb}
        patchShebangs modules/lib/nanopb/generator

        export ZEPHYR_BASE="$PWD/zephyr"
        west build -s zmk/app -d build -b seeeduino_xiao_ble \
          ${lib.optionalString isLeft "-S studio-rpc-usb-uart"} -- \
          -DZephyr_DIR="$PWD/zephyr/share/zephyr-package/cmake" \
          -DZMK_CONFIG="$configRoot/config" \
          -DZMK_EXTRA_MODULES="$configRoot" \
          -DBUILD_VERSION=v0.3 \
          -DUSER_CACHE_DIR="$TMPDIR/zephyr-cache" \
          -DSHIELD=${lib.escapeShellArg shields} \
          ${lib.optionalString isLeft "-DCONFIG_ZMK_STUDIO=y"}
        runHook postBuild
      '';

      installPhase = ''
        runHook preInstall
        mkdir -p "$out"
        cp build/zephyr/zmk.uf2 "$out/toucan_${side}.uf2"
        cp ${manifest} "$out/west-manifest-frozen.yml"
        runHook postInstall
      '';

      meta = {
        description = "Toucan2 ${side} firmware";
        platforms = [
          "aarch64-darwin"
          "aarch64-linux"
          "x86_64-linux"
        ];
      };
    };
in
rec {
  left = mkFirmware "left";
  right = mkFirmware "right";
  firmware = pkgs.symlinkJoin {
    name = "toucan-firmware";
    paths = [
      left
      right
    ];
  };
}
