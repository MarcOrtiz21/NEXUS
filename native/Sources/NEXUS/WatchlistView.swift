import SwiftUI

struct WatchlistView: View {
    @EnvironmentObject private var store: NexusStore

    var body: some View {
        NexusPage {
            if store.snapshot == nil {
                NexusSkeleton(rows: 3)
            } else if store.watchlist.isEmpty {
                NexusEmptyState(
                    title: "Nada en seguimiento",
                    detail: "Abre un activo o un tema y pulsa la estrella del inspector. Aquí caben hasta 8 nombres.",
                    symbol: "star"
                )
            } else {
                VStack(alignment: .leading, spacing: 10) {
                    NexusSectionHeader(
                        title: "Lista activa",
                        detail: "\(store.watchlist.count)/8",
                        help: "No es una cartera. Solo atajos a lo que quieres vigilar."
                    )
                    ForEach(store.watchlist, id: \.self) { ticker in
                        watchRow(ticker)
                    }
                }
                .nexusCard()
            }
        }
    }

    private func watchRow(_ ticker: String) -> some View {
        HStack(spacing: 10) {
            Button {
                store.showAsset(ticker)
            } label: {
                    HStack(spacing: 12) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text(watchlistLabel(ticker))
                            .font(.subheadline.weight(.semibold))
                            .foregroundStyle(NexusTheme.text)
                        Text(ticker)
                            .font(.caption2.monospaced())
                            .foregroundStyle(NexusTheme.muted)
                    }
                    .frame(minWidth: 120, alignment: .leading)
                    NexusMiniSparkline(points: sparkline(for: ticker), width: 72, height: 28)
                    VStack(alignment: .trailing, spacing: 4) {
                        NexusScoreBar(value: watchlistScore(ticker))
                        Text(watchlistAction(ticker))
                            .font(.caption2)
                            .foregroundStyle(NexusTheme.muted)
                    }
                    Text(watchlistHint(ticker))
                        .font(.caption.monospacedDigit().weight(.semibold))
                        .foregroundStyle(NexusTheme.muted)
                        .frame(width: 72, alignment: .trailing)
                    Image(systemName: "chevron.right")
                        .font(.caption2)
                        .foregroundStyle(NexusTheme.muted)
                }
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .help("Abrir \(ticker)")

            NexusToolbarButton(
                systemImage: "star.fill",
                label: "Quitar de seguimiento",
                helpText: "Quitar de seguimiento"
            ) {
                Task { await store.toggleWatchlist(ticker) }
            }
        }
        .padding(.vertical, 4)
    }

    private func watchlistLabel(_ ticker: String) -> String {
        if let theme = store.snapshot?.rotation?.themes?.first(where: { $0.ticker == ticker }) {
            return theme.theme ?? ticker
        }
        return store.snapshot?.decision?.assetScores?[ticker]?.label ?? ticker
    }

    private func watchlistHint(_ ticker: String) -> String {
        if let asset = store.snapshot?.assets?[ticker] {
            return formatPct(asset.momentum1m)
        }
        if let theme = store.snapshot?.rotation?.themes?.first(where: { $0.ticker == ticker }) {
            return "vs SPY \(formatPct(theme.relative1mVsSpy))"
        }
        return "—"
    }

    private func watchlistScore(_ ticker: String) -> Double? {
        if let score = store.snapshot?.decision?.assetScores?[ticker]?.score {
            return Double(score)
        }
        return store.snapshot?.rotation?.themes?.first(where: { $0.ticker == ticker })?.score
    }

    private func watchlistAction(_ ticker: String) -> String {
        if let action = store.snapshot?.decision?.assetScores?[ticker]?.action, !action.isEmpty {
            return action
        }
        return store.snapshot?.rotation?.themes?.first(where: { $0.ticker == ticker })?.signal ?? "seguir"
    }

    private func sparkline(for ticker: String) -> [SparklinePoint] {
        store.snapshot?.sparklines?[ticker]
            ?? store.snapshot?.sparklines?["^\(ticker)"]
            ?? []
    }
}
