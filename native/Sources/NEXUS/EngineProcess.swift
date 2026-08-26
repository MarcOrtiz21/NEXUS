import Darwin
import Foundation

/// Arranca `uvicorn web_dashboard` desde el .venv del repo.
final class EngineProcess {
    private var process: Process?
    private let repoRoot: URL

    init(repoRoot: URL) {
        self.repoRoot = repoRoot
    }

    func start() throws {
        Self.terminateListener(port: 8765)
        if process?.isRunning == true {
            process?.terminate()
            process = nil
        }

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

    func terminate() {
        process?.terminate()
        process = nil
        Self.terminateListener(port: 8765)
    }

    static func terminateListener(port: Int) {
        let task = Process()
        task.executableURL = URL(fileURLWithPath: "/usr/sbin/lsof")
        task.arguments = ["-nP", "-iTCP:\(port)", "-sTCP:LISTEN", "-t"]
        let pipe = Pipe()
        task.standardOutput = pipe
        task.standardError = FileHandle.nullDevice
        do {
            try task.run()
            task.waitUntilExit()
        } catch {
            return
        }
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        let pids = String(data: data, encoding: .utf8)?
            .split(whereSeparator: { $0.isNewline || $0.isWhitespace })
            .compactMap { Int32($0) } ?? []
        guard !pids.isEmpty else { return }
        for pid in Set(pids) {
            kill(pid, SIGTERM)
        }
        usleep(400_000)
        for pid in Set(pids) {
            kill(pid, SIGKILL)
        }
        usleep(200_000)
    }

    deinit {
        process?.terminate()
    }
}
