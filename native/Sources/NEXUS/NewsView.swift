import SwiftUI
import AppKit

struct NewsView: View {
    @EnvironmentObject private var store: NexusStore
    @State private var filter: String = "ALL"
    @State private var selectedItem: NewsItem?

    private var items: [NewsItem] {
        let all = store.snapshot?.news?.items ?? []
        if filter == "ALL" { return all }
        return all.filter { ($0.tone ?? "").uppercased() == filter }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            ViewThatFits(in: .horizontal) {
                HStack {
                    sentimentSummary
                    Spacer()
                    filterPicker
                }
                VStack(alignment: .leading, spacing: 8) {
                    sentimentSummary
                    filterPicker
                }
            }
            .padding(.horizontal, 20)
            .padding(.vertical, 12)

            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: NexusLayout.spacing) {
                    newsMetric("TITULARES", "\(store.snapshot?.news?.items?.count ?? 0)", "analizados")
                    newsMetric("POSITIVOS", "\(toneCount("GOOD"))", "contexto favorable")
                    newsMetric("NEGATIVOS", "\(toneCount("BAD"))", "riesgo / presión")
                    newsMetric("FUENTES", "\(store.snapshot?.news?.sources?.count ?? 0)", "cobertura activa")
                }
                .padding(.horizontal, 20)
            }
            .padding(.bottom, 10)

            if let narratives = store.snapshot?.news?.narratives?.narratives, !narratives.isEmpty {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: NexusLayout.spacing) {
                        ForEach(narratives) { narrative in
                            VStack(alignment: .leading, spacing: 4) {
                                Text(narrative.topic ?? "Tema").font(.caption.weight(.bold)).foregroundStyle(NexusTheme.accent)
                                Text("\(narrative.headlineCount ?? 0) titulares · \(narrative.dominantTone ?? "NEUTRAL")")
                                    .font(.caption).foregroundStyle(NexusTheme.toneColor(narrative.dominantTone))
                                Text(narrative.sampleTitles?.first ?? "Sin muestra")
                                    .font(.caption2).foregroundStyle(NexusTheme.muted).lineLimit(2)
                            }
                            .frame(width: 210, height: 92, alignment: .topLeading)
                            .nexusCard()
                        }
                    }
                    .padding(.horizontal, 20)
                }
                .padding(.bottom, 10)
            }

            if let sources = store.snapshot?.news?.sources, !sources.isEmpty {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack {
                        ForEach(sources, id: \.self) { source in
                            Text(source)
                                .font(.caption2)
                                .padding(.horizontal, 8)
                                .padding(.vertical, 4)
                                .background(NexusTheme.cardInner)
                                .clipShape(Capsule())
                        }
                    }
                    .padding(.horizontal, 20)
                }
                .padding(.bottom, 8)
            }

            GeometryReader { proxy in
                if let selectedItem, proxy.size.width < 700 {
                    readerPane(selectedItem, compact: true)
                } else {
                    HSplitView {
                        newsList
                        if let selectedItem {
                            readerPane(selectedItem, compact: false)
                        }
                    }
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
    }

    private var sentimentSummary: some View {
        HStack(spacing: 8) {
            if let sentiment = store.snapshot?.news?.sentiment {
                Text("Sesgo: \(sentiment.dominant ?? "—")")
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(NexusTheme.toneColor(sentiment.dominant))
                Text(sentiment.details ?? "")
                    .font(.caption)
                    .foregroundStyle(NexusTheme.muted)
                    .lineLimit(1)
                    .help("El sesgo resume titulares y no sustituye al score ni a la decisión operativa.")
            }
        }
    }

    private var filterPicker: some View {
        Picker("Filtro", selection: $filter) {
            Text("Todas").tag("ALL")
            Text("Positivas").tag("GOOD")
            Text("Negativas").tag("BAD")
            Text("Mixtas").tag("MIXED")
            Text("Neutras").tag("NEUTRAL")
        }
        .pickerStyle(.segmented)
        .frame(maxWidth: 420)
    }

    private var newsList: some View {
        List(items) { item in
            Button {
                if hasOpenableURL(item.url) {
                    selectedItem = item
                }
            } label: {
                HStack(alignment: .top, spacing: 12) {
                    ToneBadge(tone: item.tone, label: item.toneLabel)
                    VStack(alignment: .leading, spacing: 4) {
                        Text(item.title)
                            .font(.body.weight(.medium))
                            .foregroundStyle(NexusTheme.text)
                            .multilineTextAlignment(.leading)
                        if let summary = item.summary, !summary.isEmpty {
                            Text(summary)
                                .font(.caption)
                                .foregroundStyle(NexusTheme.muted)
                                .lineLimit(2)
                        }
                        HStack {
                            Text(item.source ?? "RSS")
                            if let published = item.publishedAt {
                                Text("· \(newsDate(published))")
                            }
                            Image(systemName: hasOpenableURL(item.url) ? "rectangle.righthalf.inset.filled" : "link.badge.plus")
                        }
                        .font(.caption)
                        .foregroundStyle(NexusTheme.muted)
                    }
                    Spacer(minLength: 0)
                }
                .padding(.vertical, 4)
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .disabled(!hasOpenableURL(item.url))
            .opacity(hasOpenableURL(item.url) ? 1 : 0.55)
        }
        .listStyle(.inset)
        .scrollContentBackground(.hidden)
        .frame(minWidth: selectedItem == nil ? 420 : 300)
    }

    @ViewBuilder
    private func readerPane(_ item: NewsItem, compact: Bool) -> some View {
        if let rawURL = item.url, let url = URL(string: rawURL) {
            VStack(spacing: 0) {
                HStack {
                    VStack(alignment: .leading, spacing: 2) {
                        Text(item.source ?? "Noticia").font(.caption.weight(.bold))
                        Text(item.title).font(.caption).lineLimit(2)
                    }
                    Spacer()
                    Button {
                        selectedItem = nil
                    } label: {
                        Label(compact ? "Volver" : "", systemImage: compact ? "chevron.left" : "xmark")
                    }
                    .help(compact ? "Volver a noticias" : "Cerrar lector")
                }
                .padding(10)
                Divider()
                VStack(alignment: .leading, spacing: 6) {
                    Text(item.summary?.isEmpty == false
                         ? item.summary!
                         : "Esta fuente no proporciona resumen. El tono se ha estimado únicamente a partir del titular.")
                        .font(item.summary?.isEmpty == false ? .subheadline : .caption)
                        .foregroundStyle(item.summary?.isEmpty == false ? NexusTheme.text : NexusTheme.muted)
                        .fixedSize(horizontal: false, vertical: true)
                    HStack {
                        ForEach(item.linkedAssets ?? [], id: \.self) { asset in
                            Button(asset) { store.showAsset(asset) }
                                .buttonStyle(.bordered)
                                .controlSize(.mini)
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
                    Text(newsImpact(item))
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(NexusTheme.toneColor(item.tone))
                }
                .padding(10)
                .background(NexusTheme.card.opacity(0.35))
                Divider()
                NewsReaderView(url: url)
            }
            .frame(minWidth: compact ? 0 : 360, idealWidth: 520)
        }
    }

    private func hasOpenableURL(_ urlString: String?) -> Bool {
        guard let urlString, let url = URL(string: urlString) else { return false }
        return ["http", "https"].contains(url.scheme?.lowercased())
    }

    private func open(_ urlString: String?) {
        guard hasOpenableURL(urlString), let urlString, let url = URL(string: urlString) else { return }
        NSWorkspace.shared.open(url)
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
        VStack(alignment: .leading, spacing: 3) {
            Text(title).font(.caption2.weight(.bold)).foregroundStyle(NexusTheme.accent)
            Text(value).font(.title3.monospacedDigit().weight(.bold))
            Text(hint).font(.caption2).foregroundStyle(NexusTheme.muted)
        }
        .frame(width: 150, height: 78, alignment: .topLeading)
        .nexusCard()
    }

    private func toneCount(_ tone: String) -> Int {
        (store.snapshot?.news?.items ?? []).filter { ($0.tone ?? "").uppercased() == tone }.count
    }
}
