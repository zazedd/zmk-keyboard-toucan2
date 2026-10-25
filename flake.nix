{
  description = "Toucan2 ZMK build";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";

  outputs =
    { self, nixpkgs }:
    let
      inherit (nixpkgs) lib;

      systems = [
        "aarch64-darwin"
        "aarch64-linux"
        "x86_64-linux"
      ];
      forAllSystems = f: lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});

      mkBuildEnvironment =
        pkgs:
        let
          python = pkgs.python3.withPackages (
            ps: with ps; [
              west
              pyelftools
              pyyaml
              pykwalify
              packaging
              progress
              psutil
              pylink-square
              pyserial
              requests
              anytree
              intelhex
              protobuf
              grpcio-tools
            ]
          );
        in
        {
          packages = with pkgs; [
            coreutils
            git
            cmake
            ninja
            dtc
            patch
            gcc-arm-embedded
            protobuf
            python
          ];
          env = {
            ZEPHYR_TOOLCHAIN_VARIANT = "gnuarmemb";
            GNUARMEMB_TOOLCHAIN_PATH = "${pkgs.gcc-arm-embedded}";
            PYTHONNOUSERSITE = "1";
            PYTHONPATH = "${python}/${pkgs.python3.sitePackages}";
          };
        };
    in
    {
      packages = forAllSystems (
        pkgs:
        let
          buildEnvironment = mkBuildEnvironment pkgs;
          updatePython = pkgs.python3.withPackages (ps: [ ps.west ]);
          firmwarePackages = import ./nix/firmware.nix {
            inherit pkgs lib buildEnvironment;
          };
        in
        firmwarePackages
        // {
          default = firmwarePackages.firmware;
          # Compatibility command: compilation itself is a Nix derivation.
          build = pkgs.writeShellApplication {
            name = "toucan-build";
            runtimeInputs = [
              pkgs.nix
              pkgs.coreutils
            ];
            text = ''
              case "''${1:-both}" in
                -h|--help)
                  echo 'Usage: nix run .#build -- [left|right|both] [output-directory]'
                  exit 0 ;;
                left|right) target=$1 ;;
                both) target=firmware ;;
                *) echo 'Expected left, right, or both.' >&2; exit 2 ;;
              esac
              [[ $# -le 2 ]] || { echo 'Too many arguments.' >&2; exit 2; }
              output="''${2:-firmware}"
              built=$(nix build path:${self}#"$target" --no-link --print-out-paths)
              mkdir -p "$output"
              cp --remove-destination --no-preserve=mode "$built/"* "$output/"
              echo "Firmware written to $output"
            '';
          };
          update = pkgs.writeShellApplication {
            name = "toucan-update";
            runtimeInputs = [
              pkgs.nix
              pkgs.git
            ];
            runtimeEnv = {
              PYTHONNOUSERSITE = "1";
              PYTHONPATH = "${updatePython}/${pkgs.python3.sitePackages}";
              GIT_SSL_CAINFO = "${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt";
            };
            text = ''
              exec ${updatePython}/bin/python3 ${./nix/update-west.py} "$@"
            '';
          };
          flash = pkgs.writeShellApplication {
            name = "toucan-flash";
            runtimeInputs = [
              pkgs.coreutils
              pkgs.python3
            ];
            text = builtins.readFile ./scripts/flash.sh;
          };
        }
      );

      devShells = forAllSystems (pkgs: {
        default = pkgs.mkShell (mkBuildEnvironment pkgs);
      });

      apps = forAllSystems (
        pkgs:
        let
          packages = self.packages.${pkgs.stdenv.hostPlatform.system};
          mkApp = name: {
            type = "app";
            program = lib.getExe packages.${name};
            meta.description = "Toucan2 ${name}";
          };
        in
        rec {
          build = mkApp "build";
          flash = mkApp "flash";
          update = mkApp "update";
          default = build;
        }
      );

      checks = forAllSystems (pkgs: {
        update-west = pkgs.runCommand "test-update-west" { } ''
          export TOUCAN_UPDATE_SCRIPT=${./nix/update-west.py}
          ${
            pkgs.python3.withPackages (ps: [ ps.west ])
          }/bin/python3 -m unittest discover -s ${./tests} -p test_update_west.py
          touch "$out"
        '';
      });

      formatter = forAllSystems (pkgs: pkgs.nixfmt);
    };
}
