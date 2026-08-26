import Foundation
import UserNotifications

enum NexusNotifyEvent: Equatable {
    case actionChange(from: String, to: String)
    case calendarBlock(event: String?)
}

enum NexusNotify {
    static func events(previous: NativeSnapshot?, current: NativeSnapshot) -> [NexusNotifyEvent] {
        guard let previous else { return [] }
        var out: [NexusNotifyEvent] = []
        let prevAction = previous.decision?.operationalAction ?? previous.decision?.action
        let currAction = current.decision?.operationalAction ?? current.decision?.action
        if let prevAction, let currAction, prevAction != currAction {
            out.append(.actionChange(from: prevAction, to: currAction))
        }
        let prevBlock = previous.calendar?.shouldBlock == true
        let currBlock = current.calendar?.shouldBlock == true
        if currBlock && !prevBlock {
            out.append(.calendarBlock(event: current.calendar?.nextEvent?.title))
        }
        return out
    }
}

@MainActor
final class NexusNotificationCenter: NSObject, UNUserNotificationCenterDelegate {
    static let shared = NexusNotificationCenter()
    private var configured = false

    func configure() {
        guard !configured else { return }
        configured = true
        let center = UNUserNotificationCenter.current()
        center.delegate = self
        center.requestAuthorization(options: [.alert, .sound]) { _, _ in }
    }

    func notifyIfNeeded(previous: NativeSnapshot?, current: NativeSnapshot) {
        guard current.settings?.macosNotifications ?? true else { return }
        for event in NexusNotify.events(previous: previous, current: current) {
            post(event)
        }
    }

    private func post(_ event: NexusNotifyEvent) {
        let title: String
        let body: String
        switch event {
        case let .actionChange(from, to):
            title = "NEXUS — Señal operativa"
            body = "\(from) → \(to)"
        case let .calendarBlock(eventName):
            title = "NEXUS — Bloqueo de calendario"
            if let eventName, !eventName.isEmpty {
                body = "Filtro activo por \(eventName). No forzar entradas."
            } else {
                body = "Filtro de calendario activo. No forzar entradas."
            }
        }

        UNUserNotificationCenter.current().getNotificationSettings { settings in
            if settings.authorizationStatus == .authorized || settings.authorizationStatus == .provisional {
                let content = UNMutableNotificationContent()
                content.title = title
                content.body = body
                content.sound = .default
                let request = UNNotificationRequest(
                    identifier: "nexus-\(UUID().uuidString)",
                    content: content,
                    trigger: nil
                )
                UNUserNotificationCenter.current().add(request) { error in
                    if error != nil {
                        Self.osascript(title: title, body: body)
                    }
                }
            } else {
                Self.osascript(title: title, body: body)
            }
        }
    }

    nonisolated private static func osascript(title: String, body: String) {
        let script = "display notification \(json(body)) with title \(json(title)) subtitle \"NEXUS\""
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/osascript")
        process.arguments = ["-e", script]
        process.standardOutput = FileHandle.nullDevice
        process.standardError = FileHandle.nullDevice
        try? process.run()
    }

    nonisolated private static func json(_ value: String) -> String {
        let data = try? JSONEncoder().encode(value)
        return String(data: data ?? Data("\"\"".utf8), encoding: .utf8) ?? "\"\""
    }

    nonisolated func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification,
        withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void
    ) {
        completionHandler([.banner, .list, .sound])
    }
}
