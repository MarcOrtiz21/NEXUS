import SwiftUI

/// Liquid Glass nativo solo en la capa de navegación/controles, nunca en datos.
struct NexusGlassSurface: ViewModifier {
    @Environment(\.accessibilityReduceTransparency) private var reduceTransparency
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.colorSchemeContrast) private var contrast
    @AppStorage("nexus.visual.liquidGlass") private var enabled = true
    var radius: CGFloat = 10
    var selected = false
    var interactive = false

    @ViewBuilder
    func body(content: Content) -> some View {
        if #available(macOS 26.0, *), enabled, !reduceTransparency, contrast != .increased {
            content.glassEffect(
                .regular.tint(selected ? NexusTheme.accent.opacity(0.35) : nil)
                    .interactive(interactive && !reduceMotion),
                in: RoundedRectangle(cornerRadius: radius, style: .continuous)
            )
        } else {
            content
                .background(selected ? NexusTheme.accent.opacity(0.24) : NexusTheme.sidebar)
                .overlay(RoundedRectangle(cornerRadius: radius).stroke(NexusTheme.border, lineWidth: 1))
                .clipShape(RoundedRectangle(cornerRadius: radius))
        }
    }
}

struct NexusGlassGroup<Content: View>: View {
    @ViewBuilder var content: () -> Content
    @ViewBuilder var body: some View {
        if #available(macOS 26.0, *) {
            // Cero distancia de unión: los botones separados no se fusionan.
            GlassEffectContainer(spacing: 0) { content() }
        } else {
            content()
        }
    }
}

extension View {
    func nexusGlass(radius: CGFloat = 10, selected: Bool = false, interactive: Bool = false) -> some View {
        modifier(NexusGlassSurface(radius: radius, selected: selected, interactive: interactive))
    }
}
