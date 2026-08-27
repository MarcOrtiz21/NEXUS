import SwiftUI
import AppKit

struct ContentView: View {
    @EnvironmentObject private var store: NexusStore

    var body: some View {
        VStack(spacing: 0) {
            toolbar
            Divider().opacity(0.2)
            GeometryReader { proxy in
                let maxInspector = min(
                    NexusLayout.inspectorMaxWidth,
                    max(NexusLayout.inspectorMinWidth, proxy.size.width - NexusLayout.mainFloorWidth)
                )
                let shownWidth = min(
                    NexusLayout.inspectorWatchlistWidth,
                    maxInspector
                )
                HStack(spacing: 0) {
                    mainDetailColumn
                        .frame(minWidth: 0)
                        .frame(maxWidth: .infinity)
                    if let ticker = store.selectedAssetKey {
                        inspectorPane(ticker)
                            .frame(width: max(0, shownWidth - NexusLayout.inspectorEdgeInset))
                            .frame(maxHeight: .infinity)
                            .padding(.vertical, 8)
                            .padding(.trailing, NexusLayout.inspectorEdgeInset)
                            .transition(.move(edge: .trailing).combined(with: .opacity))
                    }
                }
                .animation(NexusMotion.panel, value: store.selectedAssetKey != nil)
                .clipped()
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
        .background(NexusTheme.bg.ignoresSafeArea())
        .sheet(isPresented: $store.showSettings) {
            SettingsView()
                .environmentObject(store)
        }
    }

    private func inspectorPane(_ ticker: String) -> some View {
        ZStack {
            NexusTheme.inspector
            AssetDetailView(ticker: ticker)
                .environmentObject(store)
                .id(ticker)
        }
        .background(NexusTheme.inspector)
        .clipShape(RoundedRectangle(cornerRadius: NexusLayout.cardRadius, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: NexusLayout.cardRadius, style: .continuous)
                .stroke(NexusTheme.border, lineWidth: 1)
        )
    }

    private var mainDetailColumn: some View {
        VStack(spacing: 0) {
            if store.snapshot?.blockBanner != nil {
                BlockBannerView(banner: store.snapshot!.blockBanner!, compact: true)
                    .padding(.horizontal, NexusLayout.pagePadding)
                    .padding(.vertical, 6)
            }
            if let message = store.errorMessage, !message.isEmpty {
                HStack(alignment: .top, spacing: 8) {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .foregroundStyle(NexusTheme.warn)
                    Text(message)
                        .font(.caption)
                        .foregroundStyle(NexusTheme.text)
                        .fixedSize(horizontal: false, vertical: true)
                    Spacer()
                    NexusActionButton(title: "Reintentar", systemImage: "arrow.clockwise") {
                        Task { await store.refresh(persist: false) }
                    }
                }
                .padding(.horizontal, NexusLayout.pagePadding)
                .padding(.vertical, 8)
                .background(NexusTheme.warn.opacity(0.12))
            }
            Group {
                if store.loading && store.snapshot == nil {
                    VStack(alignment: .leading, spacing: 10) {
                        NexusSkeleton(rows: 4)
                        Text(store.engineStatus)
                            .font(.caption)
                            .foregroundStyle(NexusTheme.muted)
                    }
                    .padding(NexusLayout.pagePadding)
                } else if store.snapshot == nil {
                    VStack(alignment: .leading, spacing: 12) {
                        NexusEmptyState(
                            title: "Sin datos todavía",
                            detail: store.errorMessage ?? "El motor no ha devuelto un snapshot. Reintenta; si Yahoo tarda, se usará la última caché local.",
                            symbol: "wifi.exclamationmark"
                        )
                        NexusActionButton(title: "Reintentar", systemImage: "arrow.clockwise", role: .prominent) {
                            Task { await store.refresh(persist: false) }
                        }
                    }
                    .padding(NexusLayout.pagePadding)
                } else {
                    pageBody
                        .id(store.selected)
                        .transition(.opacity)
                }
            }
            .animation(NexusMotion.page, value: store.selected)
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .clipped()
        }
        .background(NexusTheme.bg.ignoresSafeArea())
        .animation(NexusMotion.page, value: store.snapshot?.blockBanner != nil)
        .animation(NexusMotion.page, value: store.errorMessage)
    }

    @ViewBuilder
    private var pageBody: some View {
        switch store.selected {
        case .overview: OverviewView()
        case .news: NewsView()
        case .watchlist: WatchlistView()
        case .history: HistoryView()
        case .forexGold: ForexGoldView()
        case .rotation: RotationView()
        case .paper:
            VStack(alignment: .leading, spacing: 8) {
                Text("Cartera virtual desactivada")
                    .font(.title3.weight(.bold))
                Text("Esta sección está oculta por ahora. Puedes seguir usando Resumen, Rotación e Informe.")
                    .foregroundStyle(NexusTheme.muted)
                NexusActionButton(title: "Ir a Resumen", systemImage: "gauge.with.dots.needle.67percent", role: .prominent) {
                    store.selected = .overview
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
            .padding(NexusLayout.pagePadding)
        case .global: GlobalView()
        case .report: ReportView()
        case .charts: ChartsView()
        }
    }

    private var toolbar: some View {
        HStack(alignment: .center, spacing: 10) {
            Image(nsImage: NSApplication.shared.applicationIconImage)
                .resizable()
                .interpolation(.high)
                .scaledToFit()
                .frame(width: 26, height: 26)
                .clipShape(RoundedRectangle(cornerRadius: 6, style: .continuous))
                .padding(.leading, NexusLayout.trafficLightGutter)
                .accessibilityLabel("NEXUS")

            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    toolbarGroup([.overview])
                    Divider().frame(height: 18)
                    toolbarGroup([.news, .forexGold, .rotation, .global, .charts])
                    Divider().frame(height: 18)
                    toolbarGroup([.watchlist, .history])
                }
                .padding(.vertical, 2)
                .padding(.trailing, 18)
            }
            .overlay(alignment: .trailing) {
                LinearGradient(
                    colors: [NexusTheme.sidebar.opacity(0), NexusTheme.sidebar],
                    startPoint: .leading,
                    endPoint: .trailing
                )
                .frame(width: 22)
                .allowsHitTesting(false)
            }

            Spacer(minLength: 8)

            toolbarTrailing
        }
        .padding(.trailing, 14)
        .padding(.vertical, 8)
        .frame(minHeight: 52)
        .background(NexusTheme.sidebar)
        .accessibilityElement(children: .contain)
        .accessibilityLabel("Barra de NEXUS")
    }

    private var toolbarTrailing: some View {
        HStack(spacing: 8) {
            VStack(alignment: .trailing, spacing: 1) {
                Text(store.engineStatus)
                    .font(.caption2)
                    .foregroundStyle(NexusTheme.muted)
                if let headline = store.snapshot?.freshness?.headline {
                    Text(headline)
                        .font(.caption2)
                        .foregroundStyle(NexusTheme.toneColor(store.snapshot?.freshness?.tone))
                } else if let captured = store.snapshot?.capturedAtUtc {
                    Text("Datos \(relativeAge(from: captured))")
                        .font(.caption2)
                        .foregroundStyle(NexusTheme.muted)
                }
            }
            .lineLimit(1)
            .layoutPriority(-1)

            if store.loading {
                ProgressView()
                    .controlSize(.small)
                    .help("Actualizando datos")
                    .accessibilityLabel("Actualizando datos")
            }
            StatusChipView(chip: store.snapshot?.statusChip)
                .lineLimit(1)
            NexusToolbarButton(
                systemImage: "gearshape",
                label: "Ajustes",
                helpText: "Ajustes (⌘,)"
            ) {
                store.showSettings = true
            }
            NexusToolbarButton(
                systemImage: store.loading ? "arrow.triangle.2.circlepath" : "arrow.clockwise",
                label: "Actualizar",
                helpText: "Actualizar (⌘R)",
                prominent: true,
                disabled: store.loading
            ) {
                Task { await store.refresh(persist: true) }
            }
        }
        .fixedSize(horizontal: true, vertical: false)
    }

    private func toolbarGroup(_ items: [NavItem]) -> some View {
        HStack(spacing: 2) {
            ForEach(items) { item in
                Button {
                    store.selected = item
                } label: {
                    ViewThatFits(in: .horizontal) {
                        HStack(spacing: 5) {
                            Image(systemName: item.symbol)
                            Text(LocalizedStringKey(item.rawValue))
                            Text(item.shortcutHint)
                                .font(.system(size: 9, weight: .semibold, design: .monospaced))
                                .foregroundStyle(store.selected == item ? NexusTheme.accent : NexusTheme.muted.opacity(0.75))
                        }
                        HStack(spacing: 5) {
                            Image(systemName: item.symbol)
                            Text(LocalizedStringKey(item.rawValue))
                        }
                    }
                    .font(.caption.weight(store.selected == item ? .semibold : .regular))
                    .foregroundStyle(store.selected == item ? NexusTheme.text : NexusTheme.muted)
                    .padding(.horizontal, 8)
                    .frame(minHeight: NexusLayout.toolbarButtonSize)
                    .background(
                        RoundedRectangle(cornerRadius: 8, style: .continuous)
                            .fill(store.selected == item ? NexusTheme.accent.opacity(0.22) : .clear)
                    )
                    .contentShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
                }
                .buttonStyle(.plain)
                .help("\(item.rawValue) (\(item.shortcutHint))")
                .accessibilityLabel(item.rawValue)
                .accessibilityHint("Atajo \(item.shortcutHint)")
                .accessibilityAddTraits(store.selected == item ? .isSelected : [])
            }
        }
    }

    private var subtitle: String {
        switch store.selected {
        case .overview: return "Qué hacer, bloqueos y perspectiva"
        case .news: return "Fuentes múltiples · clic para abrir · tono"
        case .watchlist: return "Hasta 8 nombres vigilados"
        case .history: return "Eventos, score, oro y forex"
        case .forexGold: return "USD/EUR, EUR/USD y oro spot"
        case .rotation: return "Qué sale del liderazgo y qué recibe el flujo"
        case .paper: return "Cartera virtual vs SPY"
        case .global: return "Mapa de mercado y factores de riesgo"
        case .report: return "Lectura ejecutiva de la última evaluación"
        case .charts: return "Terminal multipanel de mercados"
        }
    }
}
