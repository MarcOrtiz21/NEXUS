import AppKit
import UniformTypeIdentifiers

/// Exporta únicamente la vista visible de NEXUS, sin alterar datos ni capturar el escritorio.
@MainActor
enum WindowCapture {
    static func save(page: String, english: Bool) {
        guard let window = NSApplication.shared.mainWindow,
              let view = window.contentView,
              let bitmap = view.bitmapImageRepForCachingDisplay(in: view.bounds) else { return }
        view.cacheDisplay(in: view.bounds, to: bitmap)
        guard let png = bitmap.representation(using: .png, properties: [:]) else { return }

        let panel = NSSavePanel()
        panel.allowedContentTypes = [.png]
        panel.canCreateDirectories = true
        panel.title = english ? "Save visible view" : "Guardar vista visible"
        panel.message = english
            ? "Local capture with real displayed data. Check source licences and private information before publishing. No data is refreshed or changed."
            : "Captura local con los datos reales visibles. Revisa licencias de fuentes e información privada antes de publicarla. No se actualizan ni cambian datos."
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "yyyyMMdd-HHmmss"
        panel.nameFieldStringValue = "nexus-\(page)-\(formatter.string(from: Date())).png"
        panel.beginSheetModal(for: window) { response in
            guard response == .OK, let url = panel.url else { return }
            do {
                try png.write(to: url, options: .atomic)
            } catch {
                NSApplication.shared.presentError(error)
            }
        }
    }
}
