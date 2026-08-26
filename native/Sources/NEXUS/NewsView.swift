import SwiftUI
import AppKit

struct NewsView: View {
    @EnvironmentObject private var store: NexusStore
    @SceneStorage("nexus.newsReaderWidth") private var readerWidthStored = Double(NexusLayout.newsReaderIdealWidth)
    @State private var toneFilter = "ALL"
    @State private var sourceFilter = "ALL"
    @State private var topicFilter = "ALL"
    @State private var assetFilter = "ALL"

    private var readerWidth: Binding<CGFloat> {
        Binding(
            get: { CGFloat(readerWidthStored) },
            set: { readerWidthStored = Double($0) }
        )
    }

    private var allItems: [NewsItem] { store.snapshot?.news?.items ?? [] }

    private var selectedItem: NewsItem? {
        guard let id = store.selectedNewsID else { return nil }
        return allItems.first { $0.id == id }
    }

    private var items: [NewsItem] {
        allItems.filter { item in
            if toneFilter != "ALL", (item.tone ?? "").uppercased() != toneFilter { return false }
            if sourceFilter != "ALL", (item.source ?? "") != sourceFilter { return false }
            if topicFilter != "ALL", !(item.linkedTopics ?? []).contains(topicFilter) { return false }
            if assetFilter != "ALL", !(item.linkedAssets ?? []).contains(assetFilter) { return false }
            return true
        }
    }

    private var topics: [String] {
        Array(Set(allItems.flatMap { $0.linkedTopics ?? [] })).sorted()
    }

    private var assets: [String] {
        Array(Set(allItems.flatMap { $0.linkedAssets ?? [] })).sorted()
    }

    var body: some View {
        GeometryReader { proxy in
            inner
                .environment(\.nexusBreakpoint, NexusBreakpoint.from(width: proxy.size.width))
                .environment(\.nexusContentWidth, proxy.size.width)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private var inner: some View {
        VStack(alignment: .leading, spacing: 0) {
            VStack(alignment: .leading, spacing: NexusLayout.spacing) {
                HStack {
                    sentimentSummary
                    Spacer()
                    Text("Datos \(relativeAge(from: store.snapshot?.capturedAtUtc))")
                        .font(.caption)
                        .foregroundStyle(NexusTheme.muted)
                }
                NexusResponsiveGrid(wideColumns: 4, mediumColumns: 2) {
                    newsMetric("TITULARES", "\(allItems.count)", "analizados")
                    newsMetric("POSITIVOS", "\(toneCount("GOOD"))", "contexto favorable")
                    newsMetric("NEGATIVOS", "\(toneCount("BAD"))", "riesgo / presión")
                    newsMetric("FUENTES", "\(store.snapshot?.news?.sources?.count ?? 0)", "cobertura activa")
                }
                filterBar
            }
            .padding(NexusLayout.pagePadding)

            GeometryReader { proxy in
                let compact = proxy.size.width < NexusLayout.newsReaderCompactWidth
                Group {
                    if compact {
                        compactNewsStage(width: proxy.size.width)
                    } else {
                        wideNewsStage(width: proxy.size.width)
                    }
                }
                .animation(NexusMotion.panel, value: store.selectedNewsID)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private var sentimentSummary: some View {
        HStack(spacing: 8) {
            if let sentiment = store.snapshot?.news?.sentiment {
                Text("Sesgo: \(sentiment.dominant ?? "—")")
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(NexusTheme.toneColor(sentiment.dominant))
                    .help("Interpretación agregada de titulares. No sustituye al score ni a la decisión operativa.")
                Text(sentiment.details ?? "")
                    .font(.caption)
                    .foregroundStyle(NexusTheme.muted)
                    .lineLimit(1)
            }
        }
    }

    private var filterBar: some View {
        HStack(spacing: 8) {
            Picker("Tono", selection: $toneFilter) {
                Text("Todos los tonos").tag("ALL")
                Text("Positivas").tag("GOOD")
                Text("Negativas").tag("BAD")
                Text("Mixtas").tag("MIXED")
                Text("Neutras").tag("NEUTRAL")
            }
            Picker("Fuente", selection: $sourceFilter) {
                Text("Todas las fuentes").tag("ALL")
                ForEach(store.snapshot?.news?.sources ?? [], id: \.self) { Text($0).tag($0) }
            }
            Picker("Tema", selection: $topicFilter) {
                Text("Todos los temas").tag("ALL")
                ForEach(topics, id: \.self) { Text($0).tag($0) }
            }
            Picker("Activo", selection: $assetFilter) {
                Text("Todos los activos").tag("ALL")
                ForEach(assets, id: \.self) { Text($0).tag($0) }
            }
        }
        .labelsHidden()
    }

    @ViewBuilder
    private func compactNewsStage(width: CGFloat) -> some View {
        ZStack {
            if let selectedItem {
                readerPane(selectedItem, compact: true)
                    .frame(width: width)
                    .frame(maxHeight: .infinity)
                    .transition(.move(edge: .trailing).combined(with: .opacity))
            } else {
                newsList
                    .transition(.move(edge: .leading).combined(with: .opacity))
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .clipped()
    }

    private func wideNewsStage(width: CGFloat) -> some View {
        let maxReader = min(
            NexusLayout.newsReaderMaxWidth,
            max(NexusLayout.newsReaderMinWidth, width - NexusLayout.newsListMinWidth)
        )
        let shownWidth = min(CGFloat(readerWidthStored), maxReader)
        return HStack(spacing: 0) {
            newsList
                .frame(minWidth: 0)
                .frame(maxWidth: .infinity)
            if let selectedItem {
                NexusResizeHandle(
                    width: readerWidth,
                    minWidth: NexusLayout.newsReaderMinWidth,
                    maxWidth: maxReader
                )
                readerPane(selectedItem, compact: false)
                    .frame(width: shownWidth)
                    .frame(maxHeight: .infinity)
                    .transition(.move(edge: .trailing).combined(with: .opacity))
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .clipped()
    }

    private var newsList: some View {
        List(items) { item in
            Button {
                store.selectedNewsID = item.id
            } label: {
                HStack(alignment: .top, spacing: 12) {
                    ToneBadge(tone: item.tone, label: item.toneLabel)
                    VStack(alignment: .leading, spacing: 4) {
                        Text(item.title)
                            .font(.body.weight(.medium))
                            .foregroundStyle(NexusTheme.text)
                            .multilineTextAlignment(.leading)
                        HStack(spacing: 6) {
                            Text(item.source ?? "RSS")
                            if let published = item.publishedAt {
                                Text("· \(newsDate(published))")
                                    .foregroundStyle(isStale(published) ? NexusTheme.warn : NexusTheme.muted)
                            }
                            if item.summary == nil || item.summary?.isEmpty == true {
                                Text("· sin resumen")
                                    .foregroundStyle(NexusTheme.warn)
                            }
                        }
                        .font(.caption)
                        .foregroundStyle(NexusTheme.muted)
                        if selectedItem == nil, let summary = item.summary, !summary.isEmpty {
                            Text(summary)
                                .font(.caption)
                                .foregroundStyle(NexusTheme.muted)
                                .lineLimit(2)
                        }
                    }
                    Spacer(minLength: 0)
                }
                .padding(.vertical, 4)
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .listRowBackground(
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .fill(item.id == store.selectedNewsID ? NexusTheme.accent.opacity(0.14) : Color.clear)
                    .padding(.vertical, 1)
            )
        }
        .listStyle(.inset)
        .scrollContentBackground(.hidden)
        .animation(NexusMotion.page, value: store.selectedNewsID)
    }

    @ViewBuilder
    private func readerPane(_ item: NewsItem, compact: Bool) -> some View {
        VStack(spacing: 0) {
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text("NOTICIA").font(.caption2.weight(.bold)).foregroundStyle(NexusTheme.accent)
                    Text(item.source ?? "Fuente").font(.caption.weight(.bold))
                    Text(item.title).font(.caption).lineLimit(2)
                }
                Spacer()
                NexusActionButton(
                    title: compact ? "Volver" : "Cerrar",
                    systemImage: compact ? "chevron.left" : "xmark",
                    helpText: compact ? "Volver a la lista" : "Cerrar lector (Esc)"
                ) {
                    store.closeNewsReader()
                }
            }
            .padding(10)
            Divider()
            VStack(alignment: .leading, spacing: 8) {
                labeledBlock("Interpretación", newsImpact(item), NexusTheme.toneColor(item.tone))
                labeledBlock(
                    "Resumen de la fuente",
                    item.summary?.isEmpty == false ? item.summary! : "Esta fuente no proporciona resumen. El tono se ha estimado únicamente a partir del titular.",
                    item.summary?.isEmpty == false ? NexusTheme.text : NexusTheme.muted
                )
                if isStale(item.publishedAt) {
                    NexusMissingSource(title: "Titular antiguo", detail: "La captura tiene más de 24 h. Úsalo como contexto, no como dato vivo.")
                }
                HStack {
                    ForEach(item.linkedAssets ?? [], id: \.self) { asset in
                        NexusActionButton(title: asset, helpText: "Relación contextual con \(asset), no causalidad.") {
                            store.showAsset(asset)
                        }
                    }
                    ForEach((item.linkedTopics ?? []).prefix(3), id: \.self) { topic in
                        Text(topic)
                            .font(.caption2)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 3)
                            .background(NexusTheme.accent.opacity(0.12))
                            .clipShape(Capsule())
                    }
                }
            }
            .padding(10)
            .background(NexusTheme.cardInner)
            Divider()
            if let rawURL = item.url, let url = URL(string: rawURL), ["http", "https"].contains(url.scheme?.lowercased()) {
                NewsReaderView(url: url)
            } else {
                NexusEmptyState(title: "Sin enlace", detail: "Esta fuente no incluye URL abierta.", symbol: "link.badge.plus")
                    .padding()
            }
        }
        .frame(minWidth: compact ? 0 : 360, idealWidth: 520)
    }

    private func labeledBlock(_ title: String, _ text: String, _ tone: Color) -> some View {
        VStack(alignment: .leading, spacing: 3) {
            Text(title.uppercased())
                .font(.caption2.weight(.bold))
                .foregroundStyle(NexusTheme.accent)
            Text(text)
                .font(.caption)
                .foregroundStyle(tone)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    private func isStale(_ raw: String?) -> Bool {
        guard let raw, let date = ISO8601DateFormatter.nexus.date(from: raw)
                ?? ISO8601DateFormatter.nexusFractional.date(from: raw) else { return false }
        return Date().timeIntervalSince(date) > 86_400
    }

    private func newsDate(_ raw: String) -> String {
        if let date = ISO8601DateFormatter.nexus.date(from: raw)
            ?? ISO8601DateFormatter.nexusFractional.date(from: raw) {
            let seconds = max(0, Int(Date().timeIntervalSince(date)))
            if seconds < 3600 { return "hace \(max(1, seconds / 60)) min" }
            if seconds < 86_400 { return "hace \(seconds / 3600) h" }
            return "hace \(seconds / 86_400) d"
        }
        return String(raw.prefix(16))
    }

    private func newsImpact(_ item: NewsItem) -> String {
        switch (item.tone ?? "").uppercased() {
        case "GOOD":
            return "Contexto favorable; confirmar con score y tendencia antes de actuar."
        case "BAD", "PANIC":
            return "Riesgo negativo; puede reforzar una postura defensiva, pero no decide por sí solo."
        case "MIXED":
            return "Lectura mixta; evita reaccionar al titular sin revisar el contexto."
        default:
            return "Impacto incierto; úsalo como contexto, no como señal operativa."
        }
    }

    private func newsMetric(_ title: String, _ value: String, _ hint: String) -> some View {
        NexusSummaryMetricCard(title: title, value: value, hint: hint)
    }

    private func toneCount(_ tone: String) -> Int {
        allItems.filter { ($0.tone ?? "").uppercased() == tone }.count
    }
}
