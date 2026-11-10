import Foundation

/// Arranca `uvicorn web_dashboard` desde el .venv del repo.
final class EngineProcess {
    // El intérprete arranca primero sin cwd/PYTHONPATH del proyecto. Las rutas
    // se incorporan después de Py_Initialize y via argv, nunca interpoladas.
    static let bootstrapCode = """
    import os
    import sys
    print("[engine] Python inicializado", file=sys.stderr, flush=True)
    root, packages = sys.argv[1:3]
    if packages:
        sys.path.insert(0, packages)
    print("[engine] Accediendo al proyecto", file=sys.stderr, flush=True)
    os.chdir(root)
    print("[engine] Importando API", file=sys.stderr, flush=True)
    import uvicorn
    sys.path.insert(0, root)
    print("[engine] Cargando web_dashboard", file=sys.stderr, flush=True)
    uvicorn.run("web_dashboard:app", host="127.0.0.1", port=8765, reload=False)
    """
    private var process: Process?
    private var outputPipe: Pipe?
    private let diagnostics = EngineStartupDiagnostics()
    private let repoRoot: URL

    init(repoRoot: URL) {
        self.repoRoot = repoRoot
    }

    var isRunning: Bool { process?.isRunning == true }
    var startupStage: String { diagnostics.stage }

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
        let process = Process()
        // Un cwd neutro evita consultar Documentos durante la inicialización.
        // El acceso al repo posterior sigue sujeto a los permisos normales del SO.
        process.currentDirectoryURL = URL(fileURLWithPath: "/", isDirectory: true)
        let bootstrapArguments = ["-I", "-B", "-u", "-c", Self.bootstrapCode,
                                  repoRoot.path, sitePackages?.path ?? ""]
        if hasVenv {
            process.executableURL = basePython
            process.arguments = bootstrapArguments
        } else {
            process.executableURL = URL(fileURLWithPath: "/usr/bin/env")
            process.arguments = ["python3"] + bootstrapArguments
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
        ]
        for key in ["FRED_API_KEY", "NEWSAPI_KEY", "NEXUS_CALENDAR_BLOCK_HOURS", "NO_PROXY"] {
            if let value = inherited[key], !value.isEmpty {
                environment[key] = value
            }
        }
        process.environment = environment
        let pipe = Pipe()
        diagnostics.reset()
        pipe.fileHandleForReading.readabilityHandler = { [diagnostics] handle in
            let data = handle.availableData
            if data.isEmpty { handle.readabilityHandler = nil; return }
            diagnostics.consume(data)
        }
        process.standardOutput = pipe
        process.standardError = pipe
        outputPipe = pipe
        try process.run()
        self.process = process
    }

    func terminate() {
        process?.terminate()
        process = nil
        outputPipe?.fileHandleForReading.readabilityHandler = nil
        outputPipe = nil
    }

    deinit {
        process?.terminate()
    }
}

/// Solo retiene las fases estáticas del bootstrap, no URLs ni mensajes de fuentes.
private final class EngineStartupDiagnostics: @unchecked Sendable {
    private let lock = NSLock()
    private var buffer = ""
    private var lastStage = "Inicializando Python"
    var stage: String { lock.lock(); defer { lock.unlock() }; return lastStage }
    func reset() { lock.lock(); defer { lock.unlock() }; buffer = ""; lastStage = "Inicializando Python" }
    func consume(_ data: Data) {
        lock.lock(); defer { lock.unlock() }
        buffer += String(decoding: data, as: UTF8.self)
        while let newline = buffer.firstIndex(of: "\n") {
            let line = String(buffer[..<newline])
            buffer.removeSubrange(...newline)
            if line.hasPrefix("[engine] ") { lastStage = String(line.dropFirst(9)) }
        }
        if buffer.count > 2048 { buffer = "" }
    }
}
