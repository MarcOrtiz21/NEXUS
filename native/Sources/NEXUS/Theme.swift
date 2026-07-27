import SwiftUI
import AppKit

enum NexusTheme {
    static let bg = Color(red: 0.08, green: 0.08, blue: 0.09)
    static let card = Color(red: 0.17, green: 0.17, blue: 0.19)
    static let cardInner = Color(red: 0.11, green: 0.11, blue: 0.12)
    static let text = Color.white
    static let muted = Color(red: 0.60, green: 0.60, blue: 0.62)
    static let accent = Color(red: 0.04, green: 0.52, blue: 1.0)
    static let good = Color(red: 0.19, green: 0.82, blue: 0.35)
    static let warn = Color(red: 1.0, green: 0.62, blue: 0.04)
    static let bad = Color(red: 1.0, green: 0.27, blue: 0.23)

    static func toneColor(_ tone: String?) -> Color {
        let value = (tone ?? "").uppercased()
        if ["GOOD", "BULLISH", "HEALTHY", "COMPRAR", "ENTRADA"].contains(where: value.contains) {
            return good
        }
        if ["BAD", "PANIC", "BLOCKED", "VENDER", "REDUCIR", "EVITAR"].contains(where: value.contains) {
            return bad
        }
        if ["WARN", "CAUTION", "MIXED", "ESPERAR", "MANTENER", "NEUTRAL"].contains(where: value.contains) {
            return warn
        }
        return muted
    }
}

enum NexusLayout {
    static let spacing: CGFloat = 14
    static let standardCardHeight: CGFloat = 210
    static let compactCardHeight: CGFloat = 150
    static let previewCardHeight: CGFloat = 140
    static let metricCardHeight: CGFloat = 96
    static let tableRowHeight: CGFloat = 92
}

struct CardModifier: ViewModifier {
    func body(content: Content) -> some View {
        content
            .padding(14)
            .background(NexusTheme.card.opacity(0.56))
            .overlay(
                RoundedRectangle(cornerRadius: 14, style: .continuous)
                    .stroke(.white.opacity(0.12), lineWidth: 1)
            )
            .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
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
        Text(label ?? tone ?? "—")
            .font(.caption.weight(.semibold))
            .foregroundStyle(NexusTheme.toneColor(tone))
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(NexusTheme.toneColor(tone).opacity(0.18))
            .clipShape(Capsule())
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
