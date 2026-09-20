import Foundation

/// Arranca `uvicorn web_dashboard` desde el .venv del repo.
final class EngineProcess {
    private var process: Process?
    private let repoRoot: URL

    init(repoRoot: URL) {
        self.repoRoot = repoRoot
    }

    var isRunning: Bool { process?.isRunning == true }

    func start() throws {
        if process?.isRunning == true {
            process?.terminate()
            process = nil
        }

        let venvPython = repoRoot.appendingPathComponent(".venv/bin/python")
        let hasVenv = FileManager.default.isExecutableFile(atPath: venvPython.path)
        let basePython = venvPython.resolvingSymlinksInPath()
        // Evita enumerar `.venv/lib`: en macOS 27 una app GUI puede quedar
        // bloqueada dentro de `contentsOfDirectory`. La versión se deduce del
        // intérprete real (…/Versions/3.14/…) y la ruta es determinista.
        let components = basePython.pathComponents
        let version = components.firstIndex(of: "Versions").flatMap { index in
            components.indices.contains(index + 1) ? components[index + 1] : nil
        }
        let sitePackages = version.map {
            repoRoot.appendingPathComponent(".venv/lib/python\($0)/site-packages")
        }
        let pythonHome = basePython.deletingLastPathComponent().deletingLastPathComponent()
        // LaunchServices puede bloquear tanto la lectura de pyvenv.cfg como la
        // autodetección de la biblioteca estándar. Se usa el binario real con
        // PYTHONHOME y PYTHONPATH explícitos: no hay búsquedas de prefijo ni
        // enumeración del venv durante Py_Initialize.
        let launchPython = basePython

        let process = Process()
        // No usar currentDirectoryURL aquí: en macOS 27 un proceso GUI puede
        // quedar esperando indefinidamente dentro de getcwd(). El shell cambia
        // de carpeta después de inicializarse y recibe las rutas como argumentos.
        process.executableURL = URL(fileURLWithPath: "/bin/zsh")
        if hasVenv {
            // El launcher framework de Python 3.14 puede bloquearse intentando
            // abrir pyvenv.cfg cuando nace de una app GUI. Se usa el intérprete
            // real y se incorpora únicamente site-packages del entorno local.
            process.arguments = [
                "-c", "echo \"[engine] iniciando entorno local · PYTHONPATH=${PYTHONPATH:-ausente}\" >&2; cd \"$1\" || exit 72; exec \"$2\" -m uvicorn web_dashboard:app --host 127.0.0.1 --port 8765",
                "nexus-engine", repoRoot.path, launchPython.path,
            ]
        } else {
            process.arguments = [
                "-c", "cd \"$1\" && exec /usr/bin/env python3 -m uvicorn web_dashboard:app --host 127.0.0.1 --port 8765",
                "nexus-engine", repoRoot.path,
            ]
        }
        let inherited = ProcessInfo.processInfo.environment
        // Una app abierta desde un IDE o un agente puede heredar cientos de
        // variables internas. Python 3.14 puede quedar bloqueado resolviendo
        // el entorno virtual antes de importar Uvicorn. Se entrega un entorno
        // mínimo y se conservan únicamente los ajustes públicos de NEXUS.
        var environment: [String: String] = [
            "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
            "HOME": NSHomeDirectory(),
            "LANG": inherited["LANG"] ?? "en_US.UTF-8",
            "TMPDIR": inherited["TMPDIR"] ?? NSTemporaryDirectory(),
            "USER": inherited["USER"] ?? NSUserName(),
            "LOGNAME": inherited["LOGNAME"] ?? NSUserName(),
            "NEXUS_ROOT": repoRoot.path,
            "PYTHONUNBUFFERED": "1",
            "PYTHONNOUSERSITE": "1",
            "PYTHONHOME": pythonHome.path,
        ]
        if let sitePackages {
            environment["PYTHONPATH"] = [repoRoot.path, sitePackages.path].joined(separator: ":")
        }
        for key in ["FRED_API_KEY", "NEWSAPI_KEY", "NEXUS_CALENDAR_BLOCK_HOURS", "NO_PROXY"] {
            if let value = inherited[key], !value.isEmpty {
                environment[key] = value
            }
        }
        process.environment = environment
        try process.run()
        self.process = process
    }

    func terminate() {
        process?.terminate()
        process = nil
    }

    deinit {
        process?.terminate()
    }
}
