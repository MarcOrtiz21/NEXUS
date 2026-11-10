import Foundation

enum PresentationPolicy {
    /// En Resumen, la columna de apoyo no crece indefinidamente con la ventana.
    /// `width` ya excluye los márgenes de la página y el hueco entre columnas.
    static func overviewSidebarWidth(availableWidth width: CGFloat) -> CGFloat? {
        let sidebar = min(380, max(300, width * 0.25))
        return width - sidebar >= 740 ? sidebar : nil
    }

    /// Cuatro bandas visuales iguales, pero umbrales numéricos desiguales.
    static func vixPosition(_ value: Double) -> Double {
        guard value.isFinite else { return 0 }
        if value < 15 { return max(0, value / 15) * 0.25 }
        if value < 20 { return 0.25 + (value - 15) / 5 * 0.25 }
        if value < 30 { return 0.5 + (value - 20) / 10 * 0.25 }
        return 0.75 + min(1, max(0, (value - 30) / 20)) * 0.25
    }

    static func reloadChart(status: String?, loadedAt: Date?, now: Date) -> Bool {
        guard let loadedAt else { return true }
        let age = now.timeIntervalSince(loadedAt)
        let expired = ["stale", "error", "unknown"].contains((status ?? "unknown").lowercased())
        return age >= (expired ? 2 : 60)
    }

    static func denseChart(pointCount: Int, width: Double) -> Bool {
        Double(pointCount) > max(120, width / 3)
    }
}
