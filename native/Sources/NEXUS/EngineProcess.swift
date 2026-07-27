import Foundation

/// Arranca `uvicorn web_dashboard` desde el .venv del repo.
final class EngineProcess {
    private var process: Process?
    private let repoRoot: URL

    init(repoRoot: URL) {
        self.repoRoot = repoRoot
    }

    func start() throws {
        if process?.isRunning == true { return }

        let venvPython = repoRoot.appendingPathComponent(".venv/bin/python")
        let python = FileManager.default.isExecutableFile(atPath: venvPython.path)
            ? venvPython.path
            : "/usr/bin/env"

        let process = Process()
        process.currentDirectoryURL = repoRoot
        process.executableURL = URL(fileURLWithPath: python)
        if python == "/usr/bin/env" {
            process.arguments = ["python3", "-m", "uvicorn", "web_dashboard:app", "--host", "127.0.0.1", "--port", "8765"]
        } else {
            process.arguments = ["-m", "uvicorn", "web_dashboard:app", "--host", "127.0.0.1", "--port", "8765"]
        }
        var environment = ProcessInfo.processInfo.environment
        // Cursor y algunos launchers Python exportan esta variable apuntando al
        // intérprete del proceso padre. Si se hereda, Python puede bloquearse
        // durante Py_Initialize antes de llegar a Uvicorn.
        environment.removeValue(forKey: "__PYVENV_LAUNCHER__")
        environment.removeValue(forKey: "PYTHONHOME")
        environment.removeValue(forKey: "PYTHONPATH")
        environment.removeValue(forKey: "ELECTRON_RUN_AS_NODE")
        environment["PYTHONUNBUFFERED"] = "1"
        process.environment = environment
        try process.run()
        self.process = process
    }

    deinit {
        process?.terminate()
    }
}
