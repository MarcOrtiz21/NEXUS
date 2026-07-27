import SwiftUI

struct NexusAdaptiveGrid<Content: View>: View {
    let minimumWidth: CGFloat
    let spacing: CGFloat
    let content: Content

    init(
        minimumWidth: CGFloat = 300,
        spacing: CGFloat = NexusLayout.spacing,
        @ViewBuilder content: () -> Content
    ) {
        self.minimumWidth = minimumWidth
        self.spacing = spacing
        self.content = content()
    }

    var body: some View {
        LazyVGrid(
            columns: [GridItem(.adaptive(minimum: minimumWidth), spacing: spacing, alignment: .top)],
            alignment: .leading,
            spacing: spacing
        ) {
            // No aplicar modificadores al `content` compuesto: SwiftUI lo convertiría
            // en una única celda, superponiendo las tarjetas que entrega el ViewBuilder.
            content
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

struct NexusSectionHeader: View {
    let title: String
    var detail: String? = nil
    var help: String? = nil

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 6) {
            Text(title.uppercased())
                .font(.caption.weight(.bold))
                .foregroundStyle(NexusTheme.accent)
            if let detail {
                Text(detail)
                    .font(.caption2)
                    .foregroundStyle(NexusTheme.muted)
            }
            if let help {
                Image(systemName: "questionmark.circle")
                    .font(.caption2)
                    .foregroundStyle(NexusTheme.muted)
                    .help(help)
                    .accessibilityLabel(help)
            }
            Spacer(minLength: 0)
        }
    }
}

struct NexusKVRow: View {
    let label: String
    let value: String
    var tone: Color = NexusTheme.text
    var help: String? = nil

    var body: some View {
        HStack {
            HStack(spacing: 4) {
                Text(label)
                if let help {
                    Image(systemName: "questionmark.circle")
                        .font(.system(size: 9))
                        .help(help)
                }
            }
            .foregroundStyle(NexusTheme.muted)
            Spacer()
            Text(value)
                .fontWeight(.semibold)
                .foregroundStyle(tone)
                .monospacedDigit()
                .lineLimit(2)
                .multilineTextAlignment(.trailing)
                .fixedSize(horizontal: false, vertical: true)
        }
        .font(.caption)
    }
}

struct NexusSummaryMetricCard: View {
    let title: String
    let value: String
    let hint: String
    var tone: Color = NexusTheme.text
    var help: String? = nil

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            NexusSectionHeader(title: title, help: help)
            Text(value)
                .font(.title2.monospacedDigit().weight(.bold))
                .foregroundStyle(tone)
            Text(hint)
                .font(.caption2)
                .foregroundStyle(NexusTheme.muted)
                .lineLimit(2)
        }
        .nexusCard()
        .frame(maxWidth: .infinity, minHeight: NexusLayout.metricCardHeight, alignment: .topLeading)
    }
}

struct NexusGuidanceCard: View {
    let doing: String
    let avoiding: String
    var changes: String? = nil

    var body: some View {
        NexusAdaptiveGrid(minimumWidth: 240, spacing: 18) {
            guidance("QUÉ HACER", "checkmark.circle.fill", NexusTheme.good, doing)
            guidance("QUÉ EVITAR", "xmark.circle.fill", NexusTheme.bad, avoiding)
            if let changes, !changes.isEmpty {
                guidance("QUÉ CAMBIARÍA LA SEÑAL", "arrow.triangle.swap", NexusTheme.warn, changes)
            }
        }
        .nexusCard()
    }

    private func guidance(_ title: String, _ symbol: String, _ tone: Color, _ text: String) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Label(title, systemImage: symbol)
                .font(.caption.weight(.bold))
                .foregroundStyle(tone)
            Text(text)
                .font(.subheadline)
                .fixedSize(horizontal: false, vertical: true)
        }
        .frame(maxWidth: .infinity, alignment: .topLeading)
    }
}

struct NexusEmptyState: View {
    let title: String
    let detail: String
    var symbol: String = "tray"

    var body: some View {
        VStack(spacing: 8) {
            Image(systemName: symbol)
                .font(.title2)
                .foregroundStyle(NexusTheme.muted)
            Text(title).font(.headline)
            Text(detail)
                .font(.caption)
                .foregroundStyle(NexusTheme.muted)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity, minHeight: 120)
        .nexusCard()
    }
}

struct NexusScoreBar: View {
    let value: Double?
    var range: ClosedRange<Double> = 0...100
    var showValue = true

    var body: some View {
        HStack(spacing: 8) {
            ProgressView(value: clampedValue, total: range.upperBound - range.lowerBound)
                .tint(tone)
            if showValue {
                Text(value.map { String(format: "%.0f", $0) } ?? "—")
                    .font(.caption.monospacedDigit().weight(.bold))
                    .foregroundStyle(tone)
                    .frame(width: 28, alignment: .trailing)
            }
        }
    }

    private var clampedValue: Double {
        guard let value else { return 0 }
        return min(range.upperBound, max(range.lowerBound, value)) - range.lowerBound
    }

    private var tone: Color {
        guard let value else { return NexusTheme.muted }
        let progress = (value - range.lowerBound) / (range.upperBound - range.lowerBound)
        if progress >= 0.65 { return NexusTheme.good }
        if progress >= 0.45 { return NexusTheme.warn }
        return NexusTheme.bad
    }
}
