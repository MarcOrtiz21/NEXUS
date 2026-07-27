import SwiftUI

struct ContentView: View {
    @EnvironmentObject private var store: NexusStore
    @State private var columnVisibility: NavigationSplitViewVisibility = .all

    var body: some View {
        NavigationSplitView(columnVisibility: $columnVisibility) {
            List(selection: $store.selected) {
                Section("NEXUS") {
                    ForEach(NavItem.allCases) { item in
                        Label(item.rawValue, systemImage: item.symbol)
                            .tag(item)
                    }
                }
            }
            .listStyle(.sidebar)
            .scrollContentBackground(.hidden)
            .background(
                GlassBackground(
                    material: .sidebar,
                    tintOpacity: 0.14,
                    blendingMode: .withinWindow
                )
            )
            .navigationSplitViewColumnWidth(min: 180, ideal: 200, max: 240)
            .safeAreaInset(edge: .bottom) {
                VStack(alignment: .leading, spacing: 4) {
                    Text(store.engineStatus)
                        .font(.caption2)
                        .foregroundStyle(NexusTheme.muted)
                    if let captured = store.snapshot?.capturedAtUtc {
                        Text("Datos \(relativeAge(from: captured))")
                            .font(.caption2)
                            .foregroundStyle(NexusTheme.muted)
                    }
                    if let err = store.errorMessage {
                        Text(err)
                            .font(.caption2)
                            .foregroundStyle(NexusTheme.bad)
                            .lineLimit(3)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(12)
            }
        } detail: {
            VStack(spacing: 0) {
                header
                Divider().opacity(0.2)
                if let banner = store.snapshot?.blockBanner {
                    BlockBannerView(banner: banner, compact: store.selected != .overview)
                        .padding(.horizontal, 20)
                        .padding(.vertical, store.selected == .overview ? 10 : 6)
                }
                Group {
                    switch store.selected {
                    case .overview: OverviewView()
                    case .news: NewsView()
                    case .history: HistoryView()
                    case .forexGold: ForexGoldView()
                    case .rotation: RotationView()
                    case .paper: PaperView()
                    case .global: GlobalView()
                    case .report: ReportView()
                    }
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .clipped()
            }
        }
        .background(
            GlassBackground(
                material: .underWindowBackground,
                tintOpacity: 0.26,
                blendingMode: .behindWindow
            )
            .ignoresSafeArea()
        )
        .inspector(
            isPresented: Binding(
                get: { store.selectedAssetKey != nil },
                set: { if !$0 { store.closeAssetInspector() } }
            )
        ) {
            if let ticker = store.selectedAssetKey {
                AssetDetailView(ticker: ticker)
                    .environmentObject(store)
                    .inspectorColumnWidth(min: 330, ideal: 380, max: 460)
            }
        }
    }

    private var header: some View {
        ViewThatFits(in: .horizontal) {
            HStack(alignment: .center, spacing: 12) {
                headerTitle
                Spacer(minLength: 8)
                headerControls
            }
            VStack(alignment: .leading, spacing: 8) {
                headerTitle
                headerControls
            }
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 12)
    }

    private var headerTitle: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(store.selected.rawValue)
                .font(.system(size: 24, weight: .bold, design: .rounded))
            Text(subtitle)
                .font(.caption)
                .foregroundStyle(NexusTheme.muted)
        }
    }

    private var headerControls: some View {
        HStack(spacing: 8) {
            if store.loading {
                ProgressView()
                    .controlSize(.small)
                    .help("Actualizando datos")
            }
            StatusChipView(chip: store.snapshot?.statusChip)
                .lineLimit(1)
            Button {
                Task { await store.refresh(persist: true) }
            } label: {
                Image(systemName: store.loading ? "arrow.triangle.2.circlepath" : "arrow.clockwise")
            }
            .buttonStyle(.borderedProminent)
            .tint(NexusTheme.accent)
            .disabled(store.loading)
        }
        .fixedSize(horizontal: true, vertical: false)
    }

    private var subtitle: String {
        switch store.selected {
        case .overview: return "Acción, bloqueos y comparativa"
        case .news: return "Fuentes múltiples · clic para abrir · tono"
        case .history: return "Eventos, score, oro y forex"
        case .forexGold: return "EUR/USD y GLD con histórico"
        case .rotation: return "Flujos sectoriales"
        case .paper: return "Cartera virtual vs SPY"
        case .global: return "Mapa de mercado y factores de riesgo"
        case .report: return "Lectura ejecutiva de la última evaluación"
        }
    }
}
