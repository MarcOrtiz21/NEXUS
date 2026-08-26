import SwiftUI
import AppKit

enum NexusTheme {
    // Superficies sólidas: el contraste debe depender del sistema visual de
    // NEXUS, no del escritorio que haya detrás de la ventana.
    static let bg = Color(red: 0.08, green: 0.08, blue: 0.09)
    static let sidebar = Color(red: 0.105, green: 0.105, blue: 0.115)
    static let inspector = Color(red: 0.115, green: 0.115, blue: 0.125)
    static let card = Color(red: 0.17, green: 0.17, blue: 0.19)
    static let cardInner = Color(red: 0.115, green: 0.115, blue: 0.13)
    static let border = Color.white.opacity(0.12)
    static let text = Color.white
    static let muted = Color(red: 0.72, green: 0.72, blue: 0.74)
    static let accent = Color(red: 0.04, green: 0.52, blue: 1.0)
    static let good = Color(red: 0.19, green: 0.82, blue: 0.35)
    static let warn = Color(red: 1.0, green: 0.62, blue: 0.04)
    static let bad = Color(red: 1.0, green: 0.27, blue: 0.23)

    static func toneColor(_ tone: String?) -> Color {
        let value = (tone ?? "").uppercased()
        if ["GOOD", "BULLISH", "HEALTHY", "COMPRAR", "ENTRADA", "ALTA", "FUERTE"].contains(where: value.contains) {
            return good
        }
        if ["BAD", "PANIC", "BLOCKED", "VENDER", "REDUCIR", "EVITAR", "BAJA", "DEBIL", "DÉBIL"].contains(where: value.contains) {
            return bad
        }
        if ["WARN", "CAUTION", "MIXED", "ESPERAR", "MANTENER", "NEUTRAL", "MEDIA", "OBSERVAR"].contains(where: value.contains) {
            return warn
        }
        return muted
    }

    static func actionSymbol(_ action: String?) -> String {
        let value = (action ?? "").uppercased()
        if value.contains("COMPRAR") || value.contains("ENTRADA") || value.contains("FUERTE") { return "arrow.up.right.circle.fill" }
        if value.contains("VENDER") || value.contains("REDUCIR") || value.contains("EVITAR") || value.contains("DEBIL") { return "arrow.down.right.circle.fill" }
        if value.contains("ESPERAR") || value.contains("MANTENER") || value.contains("OBSERVAR") { return "pause.circle.fill" }
        return "circle"
    }
}

enum NexusBreakpoint: Equatable {
    case narrow
    case medium
    case wide

    static func from(width: CGFloat) -> NexusBreakpoint {
        if width < 820 { return .narrow }
        if width < 1180 { return .medium }
        return .wide
    }

    var columns: Int {
        switch self {
        case .narrow: return 1
        case .medium: return 2
        case .wide: return 3
        }
    }
}

private struct NexusBreakpointKey: EnvironmentKey {
    static let defaultValue: NexusBreakpoint = .wide
}

private struct NexusContentWidthKey: EnvironmentKey {
    static let defaultValue: CGFloat = 1200
}

extension EnvironmentValues {
    var nexusBreakpoint: NexusBreakpoint {
        get { self[NexusBreakpointKey.self] }
        set { self[NexusBreakpointKey.self] = newValue }
    }

    var nexusContentWidth: CGFloat {
        get { self[NexusContentWidthKey.self] }
        set { self[NexusContentWidthKey.self] = newValue }
    }
}

enum NexusLayout {
    static let spacing: CGFloat = 14
    static let pagePadding: CGFloat = 20
    static let cardRadius: CGFloat = 14
    static let cardPadding: CGFloat = 14
    static let titleSize: CGFloat = 24
    static let standardCardHeight: CGFloat = 210
    static let compactCardHeight: CGFloat = 150
    static let previewCardHeight: CGFloat = 140
    static let metricCardHeight: CGFloat = 96
    static let tableRowHeight: CGFloat = 92
    static let inspectorMinWidth: CGFloat = 380
    static let inspectorIdealWidth: CGFloat = 520
    static let inspectorMaxWidth: CGFloat = 760
    static let mainMinWidth: CGFloat = 480
    static let mainFloorWidth: CGFloat = 320
    static let newsReaderMinWidth: CGFloat = 360
    static let newsReaderIdealWidth: CGFloat = 480
    static let newsReaderMaxWidth: CGFloat = 720
    static let newsReaderCompactWidth: CGFloat = 640
    static let newsListMinWidth: CGFloat = 280
    /// Hueco izquierdo para los semáforos nativos con titlebar oculta.
    static let trafficLightGutter: CGFloat = 78
    static let toolbarButtonSize: CGFloat = 28
}

enum NexusMotion {
    static let duration: Double = 0.22
    static let panel = Animation.easeInOut(duration: duration)
    static let page = Animation.easeInOut(duration: 0.18)
}

enum NexusChartInterval: String, CaseIterable, Identifiable {
    case oneMinute = "1m"
    case fiveMinutes = "5m"
    case fifteenMinutes = "15m"
    case oneHour = "1h"
    case fourHours = "4h"
    case oneDay = "1d"
    case oneWeek = "1wk"

    var id: String { rawValue }

    var label: String {
        switch self {
        case .oneMinute: return "1 min"
        case .fiveMinutes: return "5 min"
        case .fifteenMinutes: return "15 min"
        case .oneHour: return "1 h"
        case .fourHours: return "4 h"
        case .oneDay: return "1 D"
        case .oneWeek: return "1 S"
        }
    }

    var allowedRanges: [NexusChartRange] {
        switch self {
        case .oneMinute: return [.oneDay, .fiveDays]
        case .fiveMinutes, .fifteenMinutes: return [.oneDay, .fiveDays, .oneMonth]
        case .oneHour, .fourHours: return [.oneDay, .fiveDays, .oneMonth, .threeMonths, .sixMonths, .yearToDate, .oneYear]
        case .oneDay: return NexusChartRange.allCases
        case .oneWeek: return NexusChartRange.allCases
        }
    }
}

enum NexusChartRange: String, CaseIterable, Identifiable {
    case oneDay = "1d"
    case fiveDays = "5d"
    case oneMonth = "1mo"
    case threeMonths = "3mo"
    case sixMonths = "6mo"
    case yearToDate = "ytd"
    case oneYear = "1y"
    case fiveYears = "5y"
    case maximum = "max"

    var id: String { rawValue }

    var label: String {
        switch self {
        case .oneDay: return "1D"
        case .fiveDays: return "5D"
        case .oneMonth: return "1M"
        case .threeMonths: return "3M"
        case .sixMonths: return "6M"
        case .yearToDate: return "YTD"
        case .oneYear: return "1A"
        case .fiveYears: return "5A"
        case .maximum: return "MAX"
        }
    }

    var fallbackSessions: Int {
        switch self {
        case .oneDay: return 1
        case .fiveDays: return 5
        case .oneMonth: return 22
        case .threeMonths: return 66
        case .sixMonths: return 132
        case .yearToDate, .oneYear: return 252
        case .fiveYears: return 1_260
        case .maximum: return .max
        }
    }
}

enum NexusChartStyle: String, CaseIterable, Identifiable {
    case candles
    case line
    case area

    var id: String { rawValue }
    var label: String {
        switch self {
        case .candles: return "Velas"
        case .line: return "Línea"
        case .area: return "Área"
        }
    }
}

enum NexusChartScale: String, CaseIterable, Identifiable {
    case linear
    case logarithmic

    var id: String { rawValue }
    var label: String { self == .linear ? "Lineal" : "Logarítmica" }
}

struct CardModifier: ViewModifier {
    func body(content: Content) -> some View {
        content
            .padding(NexusLayout.cardPadding)
            .background(NexusTheme.card)
            .overlay(
                RoundedRectangle(cornerRadius: NexusLayout.cardRadius, style: .continuous)
                    .stroke(NexusTheme.border, lineWidth: 1)
            )
            .clipShape(RoundedRectangle(cornerRadius: NexusLayout.cardRadius, style: .continuous))
    }
}

extension View {
    func nexusCard() -> some View {
        modifier(CardModifier())
    }

    func nexusSizedCard(_ height: CGFloat, alignment: Alignment = .topLeading) -> some View {
        frame(maxWidth: .infinity, alignment: alignment)
            .frame(minHeight: height, alignment: alignment)
    }
}

/// Vibrancy nativa de macOS (NSVisualEffectView), disponible desde macOS 14.
struct MacVibrancyView: NSViewRepresentable {
    let material: NSVisualEffectView.Material
    let blendingMode: NSVisualEffectView.BlendingMode

    func makeNSView(context: Context) -> NSVisualEffectView {
        let view = NSVisualEffectView()
        view.material = material
        view.blendingMode = blendingMode
        view.state = .active
        view.appearance = NSAppearance(named: .darkAqua)
        return view
    }

    func updateNSView(_ view: NSVisualEffectView, context: Context) {
        view.material = material
        view.blendingMode = blendingMode
    }
}

/// Superficie "liquid glass" oscura: blur nativo más una tinta para preservar
/// contraste; no es transparencia plana contra el escritorio.
struct GlassBackground: View {
    let material: NSVisualEffectView.Material
    let tintOpacity: Double
    let blendingMode: NSVisualEffectView.BlendingMode

    var body: some View {
        ZStack {
            MacVibrancyView(material: material, blendingMode: blendingMode)
            Color.black.opacity(tintOpacity)
        }
    }
}

struct ToneBadge: View {
    let tone: String?
    let label: String?

    var body: some View {
        Label(label ?? tone ?? "—", systemImage: NexusTheme.actionSymbol(tone))
            .font(.caption.weight(.semibold))
            .foregroundStyle(NexusTheme.toneColor(tone))
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(NexusTheme.toneColor(tone).opacity(0.18))
            .clipShape(Capsule())
            .accessibilityLabel(label ?? tone ?? "Sin acción")
    }
}

struct StatusChipView: View {
    let chip: StatusChip?

    var body: some View {
        Text(chip?.label ?? "—")
            .font(.caption.weight(.bold))
            .foregroundStyle(NexusTheme.toneColor(chip?.tone))
            .padding(.horizontal, 10)
            .padding(.vertical, 6)
            .background(NexusTheme.toneColor(chip?.tone).opacity(0.16))
            .clipShape(Capsule())
            .accessibilityLabel("Estado \(chip?.label ?? "desconocido")")
    }
}

enum NexusControlRole {
    case prominent
    case secondary
    case onAccent
}

struct NexusToolbarButton: View {
    let systemImage: String
    let label: String
    var helpText: String? = nil
    var prominent: Bool = false
    var disabled: Bool = false
    var role: NexusControlRole = .secondary
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Image(systemName: systemImage)
                .font(.system(size: 13, weight: .semibold))
                .frame(width: NexusLayout.toolbarButtonSize, height: NexusLayout.toolbarButtonSize)
                .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .background(NexusControlStyle.fill(prominent ? .prominent : role))
        .overlay {
            RoundedRectangle(cornerRadius: 7, style: .continuous)
                .stroke(NexusControlStyle.stroke(prominent ? .prominent : role), lineWidth: 1)
        }
        .foregroundStyle(NexusControlStyle.foreground(prominent ? .prominent : role))
        .clipShape(RoundedRectangle(cornerRadius: 7, style: .continuous))
        .disabled(disabled)
        .opacity(disabled ? 0.45 : 1)
        .help(helpText ?? label)
        .accessibilityLabel(label)
    }
}

struct NexusActionButton: View {
    let title: String
    var systemImage: String? = nil
    var role: NexusControlRole = .secondary
    var helpText: String? = nil
    var disabled: Bool = false
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 5) {
                if let systemImage {
                    Image(systemName: systemImage)
                }
                Text(title)
            }
            .font(.caption.weight(.semibold))
            .padding(.horizontal, 10)
            .frame(minHeight: NexusLayout.toolbarButtonSize)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .background(NexusControlStyle.fill(role))
        .overlay {
            RoundedRectangle(cornerRadius: 7, style: .continuous)
                .stroke(NexusControlStyle.stroke(role), lineWidth: 1)
        }
        .foregroundStyle(NexusControlStyle.foreground(role))
        .clipShape(RoundedRectangle(cornerRadius: 7, style: .continuous))
        .disabled(disabled)
        .opacity(disabled ? 0.45 : 1)
        .help(helpText ?? title)
        .accessibilityLabel(title)
    }
}

private enum NexusControlStyle {
    static func fill(_ role: NexusControlRole) -> Color {
        switch role {
        case .prominent: return NexusTheme.accent
        case .secondary: return NexusTheme.card
        case .onAccent: return Color.white.opacity(0.18)
        }
    }

    static func stroke(_ role: NexusControlRole) -> Color {
        switch role {
        case .prominent: return Color.clear
        case .secondary: return NexusTheme.border
        case .onAccent: return Color.white.opacity(0.42)
        }
    }

    static func foreground(_ role: NexusControlRole) -> Color {
        switch role {
        case .prominent: return Color.white
        case .secondary: return NexusTheme.text
        case .onAccent: return Color.white
        }
    }
}

func formatPct(_ value: Double?) -> String {
    guard let value else { return "—" }
    let sign = value > 0 ? "+" : ""
    return String(format: "%@%.2f%%", sign, value)
}

func formatDelta(_ value: Double?) -> String {
    guard let value else { return "—" }
    let sign = value > 0 ? "+" : ""
    return String(format: "%@%.1f", sign, value)
}

private enum SparklineDate {
    static let day: DateFormatter = {
        let formatter = DateFormatter()
        formatter.calendar = Calendar(identifier: .gregorian)
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = TimeZone(secondsFromGMT: 0)
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter
    }()

    static let utc: Calendar = {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = TimeZone(secondsFromGMT: 0) ?? TimeZone(identifier: "UTC") ?? .current
        return calendar
    }()
}

func sparklineDate(_ value: String?) -> Date? {
    guard let value else { return nil }
    return SparklineDate.day.date(from: String(value.prefix(10)))
}

func utcDay(_ date: Date) -> Date {
    SparklineDate.utc.startOfDay(for: date)
}

func parseFlexibleDate(_ raw: String?) -> Date? {
    guard let raw, !raw.isEmpty else { return nil }
    return ISO8601DateFormatter.nexus.date(from: raw)
        ?? ISO8601DateFormatter.nexusFractional.date(from: raw)
        ?? sparklineDate(raw)
}

func newsLinked(to ticker: String, items: [NewsItem], extra: [NewsItem] = []) -> [NewsItem] {
    let key = ticker.uppercased()
    var seen = Set<String>()
    var out: [NewsItem] = []
    func append(_ item: NewsItem) {
        if seen.insert(item.id).inserted {
            out.append(item)
        }
    }
    extra.forEach(append)
    for item in items {
        let linked = (item.linkedAssets ?? []) + (item.linkedCompanies ?? [])
        if linked.contains(where: { $0.uppercased() == key }) {
            append(item)
            continue
        }
        let blob = [item.title, item.summary].compactMap { $0?.uppercased() }.joined(separator: " ")
        if key.count >= 3, blob.contains(key) {
            append(item)
        }
    }
    return out
}

func relativeAge(from iso: String?) -> String {
    guard let iso, let date = ISO8601DateFormatter.nexus.date(from: iso)
            ?? ISO8601DateFormatter.nexusFractional.date(from: iso) else {
        return "sin datos"
    }
    let seconds = max(0, Int(Date().timeIntervalSince(date)))
    if seconds < 60 { return "hace \(seconds)s" }
    if seconds < 3600 { return "hace \(seconds / 60)m" }
    return "hace \(seconds / 3600)h"
}

func companyTechnicalNormalized(_ action: String?) -> String {
    switch (action ?? "").uppercased() {
    case "COMPRAR", "FUERTE":
        return "FUERTE"
    case "VENDER", "DEBIL", "DÉBIL":
        return "DEBIL"
    case "SIN DATOS":
        return "SIN DATOS"
    default:
        return "OBSERVAR"
    }
}

func companyTechnicalLabel(_ action: String?, allowsEntry: Bool) -> String {
    switch companyTechnicalNormalized(action) {
    case "FUERTE":
        return allowsEntry ? "Técnicamente fuerte" : "Técnicamente fuerte · no autorizado"
    case "DEBIL":
        return allowsEntry ? "Técnicamente débil" : "Técnicamente débil · no es orden"
    case "SIN DATOS":
        return "Sin datos"
    default:
        return "Observar"
    }
}

func companyTechnicalTone(_ action: String?, allowsEntry: Bool) -> String {
    switch companyTechnicalNormalized(action) {
    case "FUERTE":
        return allowsEntry ? "GOOD" : "ESPERAR"
    case "DEBIL":
        return "VENDER"
    case "SIN DATOS":
        return "NEUTRAL"
    default:
        return "ESPERAR"
    }
}

extension ISO8601DateFormatter {
    static let nexus: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime]
        return f
    }()

    static let nexusFractional: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return f
    }()
}
