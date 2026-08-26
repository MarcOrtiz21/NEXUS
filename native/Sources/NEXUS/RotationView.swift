import SwiftUI

/// Mapa de rotación: primero el flujo (sale vs entra), el detalle en el inspector.
struct RotationView: View {
    @EnvironmentObject private var store: NexusStore
    @State private var bucketFilter = "Todos"
    @State private var groupFilter = "Todos"
    @State private var search = ""

    var body: some View {
        NexusPage {
            if store.snapshot?.rotationAlignment?.conflict == true {
                NexusNoticeCard(
                    title: store.snapshot?.rotationAlignment?.title ?? "La operativa no autoriza entradas",
                    detail: store.snapshot?.rotationAlignment?.detail ?? "Esto es vigilancia, no una orden de compra.",
                    actionTitle: "Ver Resumen"
                ) {
                    store.selected = .overview
                }
            }

            readingCard

            NexusResponsiveGrid(wideColumns: 2, mediumColumns: 1) {
                flowCard(
                    title: "Sale del liderazgo",
                    help: "Temas que pierden fuerza relativa. No es una orden de venta automática.",
                    themes: Array(leavingThemes.prefix(4)),
                    empty: "Ningún líder está corrigiendo con claridad.",
                    tone: NexusTheme.bad,
                    symbol: "arrow.down.right"
                )
                flowCard(
                    title: "Entra el flujo",
                    help: "Temas que baten a SPY. Vigilancia: el permiso operativo sigue mandando.",
                    themes: Array(enteringThemes.prefix(4)),
                    empty: "Ningún receptor bate a SPY con claridad.",
                    tone: NexusTheme.good,
                    symbol: "arrow.up.right",
                    headline: receivingHeadline
                )
            }

            mapCard
        }
    }

    private var readingCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            NexusSectionHeader(
                title: "Lectura",
                help: "Compara el momentum de cada sector con SPY. Es un mapa de flujo, no una orden."
            )
            Text(rotation?.state ?? "Sin datos suficientes de rotación")
                .font(.title2.weight(.bold))
            Text(rotation?.summary ?? "Aún no hay una lectura de rotación en esta captura.")
                .font(.subheadline)
                .foregroundStyle(NexusTheme.muted)
                .fixedSize(horizontal: false, vertical: true)
            HStack(spacing: 8) {
                contextChip(vixChipLabel, vixColor)
                contextChip(stanceChipLabel, stanceColor)
                Spacer(minLength: 0)
            }
            Text("Pulsa un tema para ver empresas, gráfico y noticias. Un titular (p. ej. Moderna) no compra el sector por sí solo.")
                .font(.caption2)
                .foregroundStyle(NexusTheme.muted)
        }
        .nexusCard()
    }

    private func flowCard(
        title: String,
        help: String,
        themes: [RotationTheme],
        empty: String,
        tone: Color,
        symbol: String,
        headline: (theme: RotationTheme, item: NewsItem)? = nil
    ) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            NexusSectionHeader(title: title, detail: "\(themes.count)", help: help)
            if themes.isEmpty {
                Text(empty)
                    .font(.caption)
                    .foregroundStyle(NexusTheme.muted)
                    .padding(.vertical, 8)
            } else {
                ForEach(themes) { theme in
                    Button {
                        openTheme(theme)
                    } label: {
                        HStack(spacing: 8) {
                            Image(systemName: symbol)
                                .font(.caption2.weight(.bold))
                                .foregroundStyle(tone)
                                .frame(width: 14)
                            VStack(alignment: .leading, spacing: 1) {
                                Text(theme.theme ?? theme.ticker ?? "—")
                                    .font(.subheadline.weight(.semibold))
                                    .foregroundStyle(isSelected(theme) ? NexusTheme.accent : NexusTheme.text)
                                    .lineLimit(1)
                                Text("\(theme.ticker ?? "") · \(theme.group ?? "")")
                                    .font(.caption2)
                                    .foregroundStyle(NexusTheme.muted)
                            }
                            Spacer(minLength: 4)
                            NexusMiniSparkline(points: sparkline(for: theme.ticker), width: 56, height: 22)
                            Text(formatPct(theme.relative1mVsSpy))
                                .font(.caption.monospacedDigit().weight(.semibold))
                                .foregroundStyle(relativeColor(theme.relative1mVsSpy))
                                .frame(width: 64, alignment: .trailing)
                        }
                        .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                    .help("Abrir \(theme.theme ?? theme.ticker ?? "tema")")
                }
            }
            if let headline {
                Button {
                    openTheme(headline.theme)
                } label: {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Titular ligado a \(headline.theme.theme ?? headline.theme.ticker ?? "el tema")")
                            .font(.caption2.weight(.semibold))
                            .foregroundStyle(NexusTheme.accent)
                        Text(headline.item.title)
                            .font(.caption)
                            .foregroundStyle(NexusTheme.text)
                            .lineLimit(2)
                        Text("Coincidencia contextual, no causalidad. Pulsa para el detalle.")
                            .font(.caption2)
                            .foregroundStyle(NexusTheme.muted)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.top, 4)
                }
                .buttonStyle(.plain)
            }
        }
        .nexusCard()
        .frame(maxWidth: .infinity, alignment: .topLeading)
    }

    private var mapCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            NexusSectionHeader(
                title: "Todos los temas",
                detail: "\(filteredThemes.count)",
                help: "Una línea por sector. El detalle (empresas, velas, noticias) está en el inspector."
            )
            filterPills
            TextField("Buscar tema, ticker o empresa", text: $search)
                .textFieldStyle(.roundedBorder)
                .help("Filtra el mapa. Return abre el único resultado.")
                .onSubmit { jumpFromSearch() }
            HStack {
                Text("Tema")
                Spacer()
                Text("1M")
                    .frame(width: 62, alignment: .trailing)
                Text("vs SPY")
                    .frame(width: 64, alignment: .trailing)
            }
            .font(.caption2.weight(.semibold))
            .foregroundStyle(NexusTheme.muted)
            .padding(.top, 2)

            if filteredThemes.isEmpty {
                Text(search.isEmpty ? "Sin temas en este filtro." : "Ningún tema coincide.")
                    .font(.caption)
                    .foregroundStyle(NexusTheme.muted)
                    .padding(.vertical, 10)
            } else {
                ForEach(filteredThemes) { theme in
                    mapRow(theme)
                    Divider().opacity(0.08)
                }
            }
        }
        .nexusCard()
    }

    private var filterPills: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 6) {
                pill("Todos", selected: bucketFilter == "Todos") { bucketFilter = "Todos" }
                pill("Entran", selected: bucketFilter == "recibiendo", tone: NexusTheme.good) { bucketFilter = "recibiendo" }
                pill("Observan", selected: bucketFilter == "neutrales", tone: NexusTheme.warn) { bucketFilter = "neutrales" }
                pill("Salen", selected: bucketFilter == "perdiendo", tone: NexusTheme.bad) { bucketFilter = "perdiendo" }
                Spacer(minLength: 0)
            }
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 6) {
                    pill("Todos los grupos", selected: groupFilter == "Todos") { groupFilter = "Todos" }
                    ForEach(groups, id: \.self) { group in
                        pill(group, selected: groupFilter == group) { groupFilter = group }
                    }
                }
            }
        }
    }

    private func pill(_ label: String, selected: Bool, tone: Color = NexusTheme.accent, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(label)
                .font(.caption2.weight(.semibold))
                .foregroundStyle(selected ? tone : NexusTheme.muted)
                .padding(.horizontal, 10)
                .frame(minHeight: NexusLayout.toolbarButtonSize)
                .background(
                    Capsule(style: .continuous)
                        .fill(selected ? tone.opacity(0.16) : Color.white.opacity(0.05))
                )
        }
        .buttonStyle(.plain)
    }

    private func mapRow(_ theme: RotationTheme) -> some View {
        Button {
            openTheme(theme)
        } label: {
            HStack(spacing: 10) {
                Circle()
                    .fill(actionColor(theme))
                    .frame(width: 7, height: 7)
                VStack(alignment: .leading, spacing: 1) {
                    Text(theme.theme ?? theme.ticker ?? "—")
                        .font(.subheadline.weight(isSelected(theme) ? .bold : .semibold))
                        .foregroundStyle(isSelected(theme) ? NexusTheme.accent : NexusTheme.text)
                        .lineLimit(1)
                    Text("\(theme.group ?? "") · \(theme.ticker ?? "")")
                        .font(.caption2)
                        .foregroundStyle(NexusTheme.muted)
                }
                .frame(minWidth: 120, alignment: .leading)
                NexusMiniSparkline(points: sparkline(for: theme.ticker), width: 64, height: 22)
                Spacer(minLength: 4)
                Text(formatPct(theme.momentum1m))
                    .font(.caption.monospacedDigit())
                    .foregroundStyle(relativeColor(theme.momentum1m))
                    .frame(width: 62, alignment: .trailing)
                Text(formatPct(theme.relative1mVsSpy))
                    .font(.caption.monospacedDigit().weight(.semibold))
                    .foregroundStyle(relativeColor(theme.relative1mVsSpy))
                    .frame(width: 64, alignment: .trailing)
                Image(systemName: "chevron.right")
                    .font(.caption2)
                    .foregroundStyle(NexusTheme.muted)
            }
            .padding(.vertical, 5)
            .padding(.horizontal, 4)
            .background(
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .fill(isSelected(theme) ? NexusTheme.accent.opacity(0.10) : .clear)
            )
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .help("Abrir \(theme.theme ?? theme.ticker ?? "tema"): empresas, gráfico y noticias")
    }

    private var rotation: Rotation? { store.snapshot?.rotation }
    private var themes: [RotationTheme] { rotation?.themes ?? [] }
    private var groups: [String] {
        Array(Set(themes.compactMap(\.group))).sorted()
    }

    private var leavingThemes: [RotationTheme] {
        themes.filter { flowBucket($0) == "perdiendo" }
            .sorted { ($0.relative1mVsSpy ?? .infinity) < ($1.relative1mVsSpy ?? .infinity) }
    }

    private var enteringThemes: [RotationTheme] {
        themes.filter { flowBucket($0) == "recibiendo" }
            .sorted { ($0.relative1mVsSpy ?? -.infinity) > ($1.relative1mVsSpy ?? -.infinity) }
    }

    private var filteredThemes: [RotationTheme] {
        var result = themes
        if bucketFilter != "Todos" {
            result = result.filter { flowBucket($0) == bucketFilter }
        }
        if groupFilter != "Todos" {
            result = result.filter { $0.group == groupFilter }
        }
        let query = searchQuery
        if !query.isEmpty {
            result = result.filter { themeMatches($0, query: query) }
        }
        return result.sorted { ($0.relative1mVsSpy ?? -.infinity) > ($1.relative1mVsSpy ?? -.infinity) }
    }

    private var vix: Double? { store.snapshot?.market?["VIX"]?.value }

    private var vixChipLabel: String {
        guard let vix else { return "VIX —" }
        let band: String
        if vix >= 28 { band = "estrés" }
        else if vix >= 20 { band = "cautela" }
        else if vix >= 15 { band = "normal" }
        else { band = "calma" }
        return String(format: "VIX %.1f · %@", vix, band)
    }

    private var vixColor: Color {
        guard let vix else { return NexusTheme.muted }
        if vix >= 28 { return NexusTheme.bad }
        if vix >= 20 { return NexusTheme.warn }
        if vix >= 15 { return NexusTheme.accent }
        return NexusTheme.good
    }

    private var stanceChipLabel: String {
        let action = store.snapshot?.decision?.operationalAction
            ?? store.snapshot?.decision?.action
            ?? "ESPERAR"
        if store.snapshot?.rotationAlignment?.conflict == true {
            return "\(action) · vigilancia, no compra"
        }
        return "Operativa \(action)"
    }

    private var stanceColor: Color {
        if store.snapshot?.rotationAlignment?.conflict == true { return NexusTheme.warn }
        return NexusTheme.muted
    }

    private var receivingHeadline: (theme: RotationTheme, item: NewsItem)? {
        let items = store.snapshot?.news?.items ?? []
        for theme in enteringThemes.prefix(4) {
            if let item = items.first(where: { newsMatches($0, theme: theme) }) {
                return (theme, item)
            }
        }
        return nil
    }

    private var searchQuery: String {
        search.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
    }

    private func themeMatches(_ theme: RotationTheme, query: String) -> Bool {
        let blob = [
            theme.theme, theme.ticker, theme.group, theme.signal,
            (theme.names ?? []).joined(separator: " "),
            (theme.companies ?? []).compactMap(\.ticker).joined(separator: " "),
            (theme.companies ?? []).compactMap(\.name).joined(separator: " "),
        ]
        .compactMap { $0?.lowercased() }
        .joined(separator: " ")
        return blob.contains(query)
    }

    private func newsMatches(_ item: NewsItem, theme: RotationTheme) -> Bool {
        let blob = [item.title, item.summary].compactMap { $0?.lowercased() }.joined(separator: " ")
        let names = (theme.names ?? []).map { $0.lowercased() }
        let tickers = (theme.companies ?? []).compactMap { $0.ticker?.lowercased() }
        return names.contains { !$0.isEmpty && blob.contains($0) }
            || tickers.contains { !$0.isEmpty && blob.contains($0) }
    }

    private func openTheme(_ theme: RotationTheme) {
        if let ticker = theme.ticker { store.showAsset(ticker) }
    }

    private func isSelected(_ theme: RotationTheme) -> Bool {
        guard let selected = store.selectedAssetKey else { return false }
        return theme.ticker?.caseInsensitiveCompare(selected) == .orderedSame
    }

    private func jumpFromSearch() {
        let query = searchQuery
        guard !query.isEmpty else { return }
        let companyHits = filteredThemes.flatMap { $0.companies ?? [] }.compactMap { company -> String? in
            guard let ticker = company.ticker else { return nil }
            if ticker.lowercased() == query { return ticker }
            if (company.name ?? "").lowercased() == query { return ticker }
            return nil
        }
        let unique = Array(Set(companyHits))
        if unique.count == 1 {
            store.showAsset(unique[0])
            return
        }
        if filteredThemes.count == 1, let ticker = filteredThemes[0].ticker {
            store.showAsset(ticker)
        }
    }

    private func sparkline(for ticker: String?) -> [SparklinePoint] {
        guard let ticker, !ticker.isEmpty else { return [] }
        return store.snapshot?.sparklines?[ticker]
            ?? store.snapshot?.sparklines?["^\(ticker)"]
            ?? []
    }

    private func flowBucket(_ theme: RotationTheme) -> String {
        let signal = (theme.signal ?? "").lowercased()
        if signal.contains("entrada") || signal.contains("mejora") { return "recibiendo" }
        if signal.contains("corrección") || signal.contains("descanso") { return "perdiendo" }
        return "neutrales"
    }

    private func actionColor(_ theme: RotationTheme) -> Color {
        switch flowBucket(theme) {
        case "recibiendo": return NexusTheme.good
        case "perdiendo": return NexusTheme.bad
        default: return NexusTheme.warn
        }
    }

    private func relativeColor(_ value: Double?) -> Color {
        guard let value else { return NexusTheme.muted }
        if value > 0 { return NexusTheme.good }
        if value < 0 { return NexusTheme.bad }
        return NexusTheme.muted
    }

    private func contextChip(_ text: String, _ tone: Color) -> some View {
        Text(text)
            .font(.caption2.weight(.semibold))
            .foregroundStyle(tone)
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(tone.opacity(0.14), in: Capsule(style: .continuous))
    }
}
