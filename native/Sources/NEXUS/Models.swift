import Foundation
import SwiftUI

enum NavItem: String, CaseIterable, Identifiable {
    case overview = "Resumen"
    case news = "Noticias"
    case watchlist = "Seguimiento"
    case history = "Historial"
    case forexGold = "Forex y oro"
    case rotation = "Rotación sectorial"
    case paper = "Cartera virtual"
    case global = "Global"
    case report = "Informe"
    case charts = "Gráficos"

    var id: String { rawValue }

    var shortcut: KeyEquivalent {
        switch self {
        case .overview: return "1"
        case .news: return "2"
        case .forexGold: return "3"
        case .rotation: return "4"
        case .global: return "5"
        case .charts: return "6"
        case .watchlist: return "7"
        case .history: return "8"
        case .report: return "9"
        case .paper: return "0"
        }
    }

    var shortcutHint: String {
        switch self {
        case .overview: return "⌘1"
        case .news: return "⌘2"
        case .forexGold: return "⌘3"
        case .rotation: return "⌘4"
        case .global: return "⌘5"
        case .charts: return "⌘6"
        case .watchlist: return "⌘7"
        case .history: return "⌘8"
        case .report: return "⌘9"
        case .paper: return "⌘0"
        }
    }

    var symbol: String {
        switch self {
        case .overview: return "gauge.with.dots.needle.67percent"
        case .news: return "newspaper"
        case .watchlist: return "star"
        case .history: return "chart.xyaxis.line"
        case .forexGold: return "coloncurrencysign.circle"
        case .rotation: return "arrow.triangle.2.circlepath"
        case .paper: return "briefcase"
        case .global: return "globe.europe.africa"
        case .report: return "doc.text"
        case .charts: return "chart.line.uptrend.xyaxis"
        }
    }
}

struct NativeSnapshot: Codable {
    let schema: String?
    let capturedAtUtc: String?
    let settings: NativeSettings?
    let status: String?
    let alerts: [String]?
    let statusChip: StatusChip?
    let blockBanner: BlockBanner?
    let decision: Decision?
    let rotation: Rotation?
    let calendar: CalendarInfo?
    let market: [String: FlexibleDouble]?
    let assets: [String: AssetMetrics]?
    let globalMarkets: [String: AssetMetrics]?
    let forex: ForexBlock?
    let gold: GoldBlock?
    let news: NewsBlock?
    let history: HistoryBlock?
    let historyPeriods: [String: HistoryBlock]?
    let comparison: ComparisonBlock?
    let rankingDelta: [String: RankingDelta]?
    let assetRanking: [RankingDelta]?
    let changeAttribution: ChangeAttribution?
    let paper: PaperBlock?
    let trackRecord: TrackRecordBlock?
    let intelligence: IntelligenceBlock?
    let sessionPlan: SessionPlan?
    let sessionDigest: SessionDigest?
    let fxDigest: FxGoldDigest?
    let rotationAlignment: RotationAlignment?
    let fxAlignment: RotationAlignment?
    let watchlist: [String]?
    let sparklines: [String: [SparklinePoint]]?
    let freshness: FreshnessBlock?

    enum CodingKeys: String, CodingKey {
        case schema
        case capturedAtUtc = "captured_at_utc"
        case settings
        case status
        case alerts
        case statusChip = "status_chip"
        case blockBanner = "block_banner"
        case decision, rotation, calendar, market, assets, forex, gold, news, history, comparison, paper, intelligence, watchlist, sparklines, freshness
        case globalMarkets = "global_markets"
        case historyPeriods = "history_periods"
        case rankingDelta = "ranking_delta"
        case assetRanking = "asset_ranking"
        case changeAttribution = "change_attribution"
        case trackRecord = "track_record"
        case sessionPlan = "session_plan"
        case sessionDigest = "session_digest"
        case fxDigest = "fx_digest"
        case rotationAlignment = "rotation_alignment"
        case fxAlignment = "fx_alignment"
    }
}

struct NativeSettings: Codable {
    var refreshIntervalSeconds: Int?
    var calendarBlockHours: Int?
    var calendarBlocksSignals: Bool?
    var sentimentBlocksSignals: Bool?
    var macosNotifications: Bool?

    enum CodingKeys: String, CodingKey {
        case refreshIntervalSeconds = "refresh_interval_seconds"
        case calendarBlockHours = "calendar_block_hours"
        case calendarBlocksSignals = "calendar_blocks_signals"
        case sentimentBlocksSignals = "sentiment_blocks_signals"
        case macosNotifications = "macos_notifications"
    }
}

struct IntelligenceBlock: Codable {
    let regime: MarketRegime?
    let anomalies: [MarketAnomaly]?
    let dataQuality: DataQualitySummary?
    let freshness: FreshnessBlock?
    let trackThesis: TrackThesis?

    enum CodingKeys: String, CodingKey {
        case regime, anomalies, freshness
        case dataQuality = "data_quality"
        case trackThesis = "track_thesis"
    }
}
struct MarketRegime: Codable { let label: String?; let tone: String?; let summary: String? }
struct MarketAnomaly: Codable { let label: String?; let value: Double?; let title: String?; let severity: String? }
struct DataQualitySummary: Codable {
    let total: Int?; let unhealthy: Int?; let critical: [String]?
    let observations: [String: String]?
}

struct FreshnessLayer: Codable, Identifiable {
    var id: String { key ?? label ?? "layer" }
    let key: String?
    let label: String?
    let ageSeconds: Double?
    let ageLabel: String?
    let status: String?
    let asOf: String?

    enum CodingKeys: String, CodingKey {
        case label, status
        case key = "id"
        case ageSeconds = "age_seconds"
        case ageLabel = "age_label"
        case asOf = "as_of"
    }
}

struct FreshnessBlock: Codable {
    let headline: String?
    let tone: String?
    let layers: [FreshnessLayer]?
}

struct TrackThesis: Codable {
    let ready: Bool?
    let tone: String?
    let headline: String?
    let detail: String?
    let sampleSize: Int?
    let buyCount: Int?
    let hitRatePct: Double?
    let avgReturnPct: Double?
    let forwardDays: Int?
    let beatsSpy: Bool?
    let buyCount20d: Int?
    let hitRate20dPct: Double?

    enum CodingKeys: String, CodingKey {
        case ready, tone, headline, detail
        case sampleSize = "sample_size"
        case buyCount = "buy_count"
        case hitRatePct = "hit_rate_pct"
        case avgReturnPct = "avg_return_pct"
        case forwardDays = "forward_days"
        case beatsSpy = "beats_spy"
        case buyCount20d = "buy_count_20d"
        case hitRate20dPct = "hit_rate_20d_pct"
    }
}

struct SessionPlanContext: Codable, Identifiable {
    var id: String { (label ?? "") + "-" + (value ?? "") }
    let label: String?
    let value: String?
}

struct SessionPlanLeg: Codable, Identifiable {
    var id: String { ticker ?? label ?? UUID().uuidString }
    let ticker: String?
    let label: String?
    let verb: String?
    let now: String?
    let nowWeight: Int?
    let openWeight: Int?
    let weightNote: String?
    let kind: String?

    enum CodingKeys: String, CodingKey {
        case ticker, label, verb, now, kind
        case nowWeight = "now_weight"
        case openWeight = "open_weight"
        case weightNote = "weight_note"
    }
}

struct SessionPlan: Codable {
    let stance: String?
    let buy: String?
    let buyLabel: String?
    let sell: String?
    let verdict: String?
    let doing: String?
    let avoiding: String?
    let changes: String?
    let allowsEntry: Bool?
    let weightCaption: String?
    let context: [SessionPlanContext]?
    let legs: [SessionPlanLeg]?
    let score: Int?
    let confidence: String?
    let confidenceNote: String?
    let scoreDrivers: [ScoreDriver]?

    enum CodingKeys: String, CodingKey {
        case stance, buy, sell, verdict, doing, avoiding, changes, context, legs, score, confidence
        case buyLabel = "buy_label"
        case allowsEntry = "allows_entry"
        case weightCaption = "weight_caption"
        case confidenceNote = "confidence_note"
        case scoreDrivers = "score_drivers"
    }
}

struct ScoreDriver: Codable, Identifiable {
    var id: String { (factor ?? "") + "-" + (detail ?? "") }
    let factor: String?
    let detail: String?
}

struct SessionDigest: Codable {
    let hasPrior: Bool?
    let baselineCapturedAt: String?
    let headline: String?
    let summary: String?
    let action: DigestChange?
    let score: DigestMetric?
    let vix: DigestMetric?
    let rotationCrossings: [RotationCrossing]?
    let rotationNote: String?

    enum CodingKeys: String, CodingKey {
        case headline, summary, action, score, vix
        case hasPrior = "has_prior"
        case baselineCapturedAt = "baseline_captured_at"
        case rotationCrossings = "rotation_crossings"
        case rotationNote = "rotation_note"
    }
}

struct DigestChange: Codable {
    let from: String?
    let to: String?
    let changed: Bool?
    let label: String?
}

struct DigestMetric: Codable {
    let from: Double?
    let to: Double?
    let delta: Double?
    let changed: Bool?
}

struct FxGoldDigest: Codable {
    let hasPrior: Bool?
    let baselineCapturedAt: String?
    let headline: String?
    let summary: String?
    let forexAction: DigestChange?
    let goldBias: DigestChange?
    let eurusd: FxPriceChange?
    let gld: FxPriceChange?

    enum CodingKeys: String, CodingKey {
        case headline, summary, eurusd, gld
        case hasPrior = "has_prior"
        case baselineCapturedAt = "baseline_captured_at"
        case forexAction = "forex_action"
        case goldBias = "gold_bias"
    }
}

struct FxPriceChange: Codable {
    let from: Double?
    let to: Double?
    let delta: Double?
    let pips: Double?
    let changed: Bool?
    let label: String?
}

struct RotationCrossing: Codable, Identifiable {
    var id: String { ticker ?? theme ?? UUID().uuidString }
    let ticker: String?
    let theme: String?
    let group: String?
    let fromBucket: String?
    let toBucket: String?
    let fromLabel: String?
    let toLabel: String?

    enum CodingKeys: String, CodingKey {
        case ticker, theme, group
        case fromBucket = "from_bucket"
        case toBucket = "to_bucket"
        case fromLabel = "from_label"
        case toLabel = "to_label"
    }
}

struct RotationAlignment: Codable {
    let conflict: Bool?
    let severity: String?
    let stance: String?
    let title: String?
    let detail: String?
    let operationalAction: String?
    let pauseReason: String?
    let receivingCount: Int?

    enum CodingKeys: String, CodingKey {
        case conflict, severity, stance, title, detail
        case operationalAction = "operational_action"
        case pauseReason = "pause_reason"
        case receivingCount = "receiving_count"
    }
}

struct StatusChip: Codable {
    let label: String
    let tone: String
    let status: String?
    let macroBlock: Bool?

    enum CodingKeys: String, CodingKey {
        case label, tone, status
        case macroBlock = "macro_block"
    }
}

struct BlockBanner: Codable {
    let severity: String?
    let title: String
    let guidance: String
    let status: String?
    let blockHours: Int?
    let eventTitle: String?
    let eventAt: String?
    let countdownSeconds: Int?
    let actionHint: String?
    let estimated: Bool?
    let timeQuality: String?
    let source: String?

    enum CodingKeys: String, CodingKey {
        case severity, title, guidance, status, estimated, source
        case blockHours = "block_hours"
        case eventTitle = "event_title"
        case eventAt = "event_at"
        case countdownSeconds = "countdown_seconds"
        case actionHint = "action_hint"
        case timeQuality = "time_quality"
    }
}

struct Decision: Codable {
    let action: String?
    let score: Int?
    let confidence: String?
    let confidenceNote: String?
    let favoredAssets: [String]?
    let allocation: [String: Int]?
    let macroAllocation: [String: Int]?
    let rationale: String?
    let macroAction: String?
    let operationalAction: String?
    let operationalPauseReason: String?
    let assetScores: [String: AssetScore]?
    let scoreBreakdown: [ScoreBreakdownItem]?

    enum CodingKeys: String, CodingKey {
        case action, score, confidence, allocation, rationale
        case confidenceNote = "confidence_note"
        case macroAllocation = "macro_allocation"
        case favoredAssets = "favored_assets"
        case macroAction = "macro_action"
        case operationalAction = "operational_action"
        case operationalPauseReason = "operational_pause_reason"
        case assetScores = "asset_scores"
        case scoreBreakdown = "score_breakdown"
    }
}

struct ScoreBreakdownItem: Codable {
    let factor: String?
    let reason: String?
}

struct AssetScore: Codable {
    let label: String?
    let score: Int?
    let action: String?
    let trend: String?
    let momentum1m: Double?
    let momentum3m: Double?
    let volatility20d: Double?

    enum CodingKeys: String, CodingKey {
        case label, score, action, trend
        case momentum1m = "momentum_1m"
        case momentum3m = "momentum_3m"
        case volatility20d = "volatility_20d"
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        label = try c.decodeIfPresent(String.self, forKey: .label)
        score = try c.decodeIfPresent(Int.self, forKey: .score)
        action = try c.decodeIfPresent(String.self, forKey: .action)
        trend = try c.decodeIfPresent(String.self, forKey: .trend)
        momentum1m = Self.number(c, .momentum1m)
        momentum3m = Self.number(c, .momentum3m)
        volatility20d = Self.number(c, .volatility20d)
    }

    private static func number(_ c: KeyedDecodingContainer<CodingKeys>, _ key: CodingKeys) -> Double? {
        if let value = try? c.decode(Double.self, forKey: key) { return value }
        if let value = try? c.decode(Int.self, forKey: key) { return Double(value) }
        return nil
    }
}

struct RankingDelta: Codable {
    let ticker: String?
    let label: String?
    let rank: Int?
    let previousRank: Int?
    let rankDelta: Int?
    let scoreDelta: Double?
    let actionFrom: String?
    let actionTo: String?

    enum CodingKeys: String, CodingKey {
        case ticker, label, rank
        case previousRank = "prior_rank"
        case rankDelta = "rank_delta"
        case scoreDelta = "score_delta"
        case actionFrom = "action_from"
        case actionTo = "action_to"
    }
}

struct ChangeAttribution: Codable {
    let topAssetMovers: [RankingDelta]?
    let rationale: AttributionTextChange?
    let note: String?

    enum CodingKeys: String, CodingKey {
        case rationale, note
        case topAssetMovers = "top_asset_movers"
    }
}

struct AttributionTextChange: Codable {
    let from: String?
    let to: String?
    let changed: Bool?
}

struct Rotation: Codable {
    let state: String?
    let summary: String?
    let leadersAvg1m: Double?
    let receiversAvg1m: Double?
    let themes: [RotationTheme]?

    enum CodingKeys: String, CodingKey {
        case state, summary, themes
        case leadersAvg1m = "leaders_avg_1m"
        case receiversAvg1m = "receivers_avg_1m"
    }
}

struct RotationTheme: Codable, Identifiable {
    var id: String { ticker ?? theme ?? UUID().uuidString }
    let ticker: String?
    let group: String?
    let theme: String?
    let represents: String?
    let signal: String?
    let score: Double?
    let momentum1m: Double?
    let momentum3m: Double?
    let relative1mVsSpy: Double?
    let trend: String?
    let price: Double?
    let ma20: Double?
    let ma50: Double?
    let ma200: Double?
    let volatility20d: Double?
    let names: [String]?
    let newsTopics: [String]?
    let companies: [RotationCompany]?
    let leadership: String?

    enum CodingKeys: String, CodingKey {
        case ticker, group, theme, represents, signal, score, trend, price, ma20, ma50, ma200, names, companies, leadership
        case momentum1m = "momentum_1m"
        case momentum3m = "momentum_3m"
        case relative1mVsSpy = "relative_1m_vs_spy"
        case volatility20d = "volatility_20d"
        case newsTopics = "news_topics"
    }
}

struct RotationCompany: Codable, Identifiable {
    var id: String { ticker ?? name ?? UUID().uuidString }
    let name: String?
    let ticker: String?
    let price: Double?
    let momentum1m: Double?
    let momentum3m: Double?
    let trend: String?
    let volatility20d: Double?
    let score: Int?
    let action: String?

    enum CodingKeys: String, CodingKey {
        case name, ticker, price, trend
        case momentum1m = "momentum_1m"
        case momentum3m = "momentum_3m"
        case volatility20d = "volatility_20d"
        case score, action
    }
}

struct SparklinePoint: Codable, Identifiable, Equatable {
    var id: String { date ?? UUID().uuidString }
    let date: String?
    let value: Double?
    let open: Double?
    let high: Double?
    let low: Double?
    let volume: Double?
    let ma20: Double?
    let ma50: Double?
    let ma200: Double?
    let relSpy: Double?
    let syntheticOHLC: Bool?
    let epochUTC: Double?
    let interval: String?
    let timezone: String?
    let session: String?
    let adjusted: Bool?
    let adjustment: String?

    enum CodingKeys: String, CodingKey {
        case date, value, open, high, low
        case volume, ma20, ma50, ma200, interval, timezone, session, adjusted, adjustment, epoch
        case epochUTC = "epoch_utc"
        case relSpy = "rel_spy"
        case syntheticOHLC = "synthetic_ohlc"
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        date = try c.decodeIfPresent(String.self, forKey: .date)
        value = Self.num(c, .value)
        open = Self.num(c, .open)
        high = Self.num(c, .high)
        low = Self.num(c, .low)
        volume = Self.num(c, .volume)
        ma20 = Self.num(c, .ma20)
        ma50 = Self.num(c, .ma50)
        ma200 = Self.num(c, .ma200)
        relSpy = Self.num(c, .relSpy)
        syntheticOHLC = try c.decodeIfPresent(Bool.self, forKey: .syntheticOHLC)
        epochUTC = Self.num(c, .epochUTC) ?? Self.num(c, .epoch)
        interval = try c.decodeIfPresent(String.self, forKey: .interval)
        timezone = try c.decodeIfPresent(String.self, forKey: .timezone)
        session = try c.decodeIfPresent(String.self, forKey: .session)
        adjusted = try? c.decodeIfPresent(Bool.self, forKey: .adjusted)
        adjustment = try c.decodeIfPresent(String.self, forKey: .adjustment)
    }

    func encode(to encoder: Encoder) throws {
        var c = encoder.container(keyedBy: CodingKeys.self)
        try c.encodeIfPresent(date, forKey: .date)
        try c.encodeIfPresent(value, forKey: .value)
        try c.encodeIfPresent(open, forKey: .open)
        try c.encodeIfPresent(high, forKey: .high)
        try c.encodeIfPresent(low, forKey: .low)
        try c.encodeIfPresent(volume, forKey: .volume)
        try c.encodeIfPresent(ma20, forKey: .ma20)
        try c.encodeIfPresent(ma50, forKey: .ma50)
        try c.encodeIfPresent(ma200, forKey: .ma200)
        try c.encodeIfPresent(relSpy, forKey: .relSpy)
        try c.encodeIfPresent(syntheticOHLC, forKey: .syntheticOHLC)
        try c.encodeIfPresent(epochUTC, forKey: .epoch)
        try c.encodeIfPresent(interval, forKey: .interval)
        try c.encodeIfPresent(timezone, forKey: .timezone)
        try c.encodeIfPresent(session, forKey: .session)
        try c.encodeIfPresent(adjusted, forKey: .adjusted)
        try c.encodeIfPresent(adjustment, forKey: .adjustment)
    }

    private static func num(_ c: KeyedDecodingContainer<CodingKeys>, _ key: CodingKeys) -> Double? {
        if let d = try? c.decode(Double.self, forKey: key) { return d }
        if let i = try? c.decode(Int.self, forKey: key) { return Double(i) }
        return nil
    }
}

struct ChartSeriesPayload: Decodable {
    let ticker: String
    let interval: String?
    let range: String?
    let points: [SparklinePoint]
    let benchmark: [SparklinePoint]?
    let asOf: String?
    let source: String?
    let status: String?
    let revision: String?
    let timezone: String?
    let session: String?
    let adjusted: Bool?
    let adjustment: String?
    let marketState: String?
    let dataStatus: String?

    enum CodingKeys: String, CodingKey {
        case ticker, interval, range, points, benchmark, source, status, revision, timezone, session, adjusted, adjustment
        case asOf = "as_of"
        case marketState = "market_state"
        case dataStatus = "data_status"
    }
}

struct CalendarEventItem: Codable, Identifiable {
    var id: String { "\(title ?? "")-\(whenUtc ?? "")" }
    let title: String?
    let whenUtc: String?
    let hoursUntil: Double?
    let impact: String?
    let source: String?
    let blocksSignals: Bool?
    let estimated: Bool?

    enum CodingKeys: String, CodingKey {
        case title, impact, source, estimated
        case whenUtc = "when_utc"
        case hoursUntil = "hours_until"
        case blocksSignals = "blocks_signals"
    }
}

struct CalendarInfo: Codable {
    let shouldBlock: Bool?
    let blockHours: Int?
    let nextEvent: FlexibleEvent?
    let upcoming: [CalendarEventItem]?
    let fxUpcoming: [CalendarEventItem]?
    let confidence: String?
    let source: String?
    let timeQuality: String?
    let estimatedWindow: Bool?

    enum CodingKeys: String, CodingKey {
        case shouldBlock = "should_block"
        case blockHours = "block_hours"
        case nextEvent = "next_event"
        case upcoming
        case fxUpcoming = "fx_upcoming"
        case confidence, source
        case timeQuality = "time_quality"
        case estimatedWindow = "estimated_window"
    }
}

/// next_event puede ser dict o string legacy
struct FlexibleEvent: Codable {
    let title: String?
    let whenUtc: String?
    let hoursUntil: Double?

    enum CodingKeys: String, CodingKey {
        case title
        case whenUtc = "when_utc"
        case hoursUntil = "hours_until"
    }

    init(from decoder: Decoder) throws {
        if let container = try? decoder.container(keyedBy: CodingKeys.self) {
            title = try container.decodeIfPresent(String.self, forKey: .title)
            whenUtc = try container.decodeIfPresent(String.self, forKey: .whenUtc)
            hoursUntil = try container.decodeIfPresent(Double.self, forKey: .hoursUntil)
            return
        }
        let single = try decoder.singleValueContainer()
        title = try? single.decode(String.self)
        whenUtc = nil
        hoursUntil = nil
    }
}

struct FlexibleDouble: Codable {
    let value: Double?

    init(from decoder: Decoder) throws {
        let c = try decoder.singleValueContainer()
        if c.decodeNil() {
            value = nil
            return
        }
        if let d = try? c.decode(Double.self) {
            value = d
            return
        }
        if let i = try? c.decode(Int.self) {
            value = Double(i)
            return
        }
        if let s = try? c.decode(String.self), let d = Double(s) {
            value = d
            return
        }
        value = nil
    }

    func encode(to encoder: Encoder) throws {
        var c = encoder.singleValueContainer()
        try c.encode(value)
    }
}

struct AssetMetrics: Codable {
    let price: Double?
    let ma20: Double?
    let ma50: Double?
    let ma200: Double?
    let momentum1m: Double?
    let momentum3m: Double?
    let volatility20d: Double?

    enum CodingKeys: String, CodingKey {
        case price
        case ma20, ma50, ma200
        case momentum1m = "momentum_1m"
        case momentum3m = "momentum_3m"
        case volatility20d = "volatility_20d"
    }

    init(
        price: Double?, ma20: Double?, ma50: Double?, ma200: Double?,
        momentum1m: Double?, momentum3m: Double?, volatility20d: Double?
    ) {
        self.price = price
        self.ma20 = ma20
        self.ma50 = ma50
        self.ma200 = ma200
        self.momentum1m = momentum1m
        self.momentum3m = momentum3m
        self.volatility20d = volatility20d
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        price = Self.num(c, .price)
        ma20 = Self.num(c, .ma20)
        ma50 = Self.num(c, .ma50)
        ma200 = Self.num(c, .ma200)
        momentum1m = Self.num(c, .momentum1m)
        momentum3m = Self.num(c, .momentum3m)
        volatility20d = Self.num(c, .volatility20d)
    }

    private static func num(_ c: KeyedDecodingContainer<CodingKeys>, _ key: CodingKeys) -> Double? {
        if let d = try? c.decode(Double.self, forKey: key) { return d }
        if let i = try? c.decode(Int.self, forKey: key) { return Double(i) }
        return nil
    }
}

struct ForexBlock: Codable {
    let EURUSD: AssetMetrics?
    let signal: ForexSignal?
    let dual: [String: String]?
    let rates: ForexRates?
    let strength: ForexPairStrength?
    let plan: ForexPlan?
    let headlines: [NewsItem]?
}

struct ForexPairStrength: Codable {
    let eur: Double?
    let usd: Double?
}

struct ForexPlan: Codable {
    let stance: String?
    let buy: String?
    let sell: String?
    let verdict: String?
    let doing: String?
    let avoiding: String?
    let changes: String?
    let allowsEntry: Bool?

    enum CodingKeys: String, CodingKey {
        case stance, buy, sell, verdict, doing, avoiding, changes
        case allowsEntry = "allows_entry"
    }
}

struct ForexRates: Codable {
    let eurUsd: Double?
    let usdEur: Double?
    let eurLabel: String?
    let usdLabel: String?

    enum CodingKeys: String, CodingKey {
        case eurUsd = "eur_usd"
        case usdEur = "usd_eur"
        case eurLabel = "eur_label"
        case usdLabel = "usd_label"
    }
}

struct ForexSignal: Codable {
    let score: Double?
    let action: String?
    let confidence: String?
    let eurTrend: String?
    let usdTrend: String?
    let rel1m: Double?
    let rel3m: Double?
    let relChange: Double?
    let evolution: String?
    let bias: String?
    let summary: String?
    let news: ForexNews?

    enum CodingKeys: String, CodingKey {
        case score, action, confidence, evolution, bias, summary, news
        case eurTrend = "eur_trend"
        case usdTrend = "usd_trend"
        case rel1m = "rel_1m"
        case rel3m = "rel_3m"
        case relChange = "rel_change"
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        if let d = try? c.decode(Double.self, forKey: .score) {
            score = d
        } else if let i = try? c.decode(Int.self, forKey: .score) {
            score = Double(i)
        } else {
            score = nil
        }
        action = try c.decodeIfPresent(String.self, forKey: .action)
        confidence = try c.decodeIfPresent(String.self, forKey: .confidence)
        eurTrend = try c.decodeIfPresent(String.self, forKey: .eurTrend)
        usdTrend = try c.decodeIfPresent(String.self, forKey: .usdTrend)
        rel1m = Self.num(c, .rel1m)
        rel3m = Self.num(c, .rel3m)
        relChange = Self.num(c, .relChange)
        evolution = try c.decodeIfPresent(String.self, forKey: .evolution)
        bias = try c.decodeIfPresent(String.self, forKey: .bias)
        summary = try c.decodeIfPresent(String.self, forKey: .summary)
        news = try c.decodeIfPresent(ForexNews.self, forKey: .news)
    }

    private static func num(_ c: KeyedDecodingContainer<CodingKeys>, _ key: CodingKeys) -> Double? {
        if let d = try? c.decode(Double.self, forKey: key) { return d }
        if let i = try? c.decode(Int.self, forKey: key) { return Double(i) }
        return nil
    }
}

struct ForexNews: Codable {
    let eurScore: Double?
    let usdScore: Double?
    let netEurMinusUsd: Double?
    let expectation: String?

    enum CodingKeys: String, CodingKey {
        case expectation
        case eurScore = "eur_score"
        case usdScore = "usd_score"
        case netEurMinusUsd = "net_eur_minus_usd"
    }
}

struct GoldBlock: Codable {
    let GLD: AssetMetrics?
    let label: String?
    let signal: GoldSignal?
}

struct GoldSignal: Codable {
    let bias: String?
    let tone: String?
    let summary: String?
    let confidence: String?
    let score: Double?
    let realRate: Double?
    let vsDollar1m: Double?
    let vsDollarNote: String?
    let vix: Double?
    let gldTrend: String?
    let usdTrend: String?
    let drivers: [String]?

    enum CodingKeys: String, CodingKey {
        case bias, tone, summary, confidence, score, drivers, vix
        case realRate = "real_rate"
        case vsDollar1m = "vs_dollar_1m"
        case vsDollarNote = "vs_dollar_note"
        case gldTrend = "gld_trend"
        case usdTrend = "usd_trend"
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        bias = try c.decodeIfPresent(String.self, forKey: .bias)
        tone = try c.decodeIfPresent(String.self, forKey: .tone)
        summary = try c.decodeIfPresent(String.self, forKey: .summary)
        confidence = try c.decodeIfPresent(String.self, forKey: .confidence)
        drivers = try c.decodeIfPresent([String].self, forKey: .drivers)
        gldTrend = try c.decodeIfPresent(String.self, forKey: .gldTrend)
        usdTrend = try c.decodeIfPresent(String.self, forKey: .usdTrend)
        if let d = try? c.decode(Double.self, forKey: .score) {
            score = d
        } else if let i = try? c.decode(Int.self, forKey: .score) {
            score = Double(i)
        } else {
            score = nil
        }
        realRate = Self.num(c, .realRate)
        vsDollar1m = Self.num(c, .vsDollar1m)
        vsDollarNote = try c.decodeIfPresent(String.self, forKey: .vsDollarNote)
        vix = Self.num(c, .vix)
    }

    private static func num(_ c: KeyedDecodingContainer<CodingKeys>, _ key: CodingKeys) -> Double? {
        if let d = try? c.decode(Double.self, forKey: key) { return d }
        if let i = try? c.decode(Int.self, forKey: key) { return Double(i) }
        return nil
    }
}

struct NewsBlock: Codable {
    let items: [NewsItem]?
    let count: Int?
    let sources: [String]?
    let sentiment: NewsSentiment?
    let narratives: NewsNarratives?
}

struct NewsNarratives: Codable {
    let narratives: [NewsNarrative]?
    let note: String?
}
struct NewsNarrative: Codable, Identifiable {
    var id: String { topic ?? UUID().uuidString }
    let topic: String?
    let headlineCount: Int?
    let dominantTone: String?
    let linkedAssets: [String]?
    let sampleTitles: [String]?
    enum CodingKeys: String, CodingKey {
        case topic
        case headlineCount = "headline_count"
        case dominantTone = "dominant_tone"
        case linkedAssets = "linked_assets"
        case sampleTitles = "sample_titles"
    }
}

struct NewsItem: Codable, Identifiable {
    var id: String { (url?.isEmpty == false ? url! : title) + (publishedAt ?? "") }
    let title: String
    let source: String?
    let url: String?
    let publishedAt: String?
    let tone: String?
    let toneLabel: String?
    let summary: String?
    let linkedTopics: [String]?
    let eventTopics: [String]?
    let linkedAssets: [String]?
    let linkedCompanies: [String]?

    enum CodingKeys: String, CodingKey {
        case title, source, url, tone, summary
        case publishedAt = "published_at"
        case toneLabel = "tone_label"
        case linkedTopics = "linked_topics"
        case eventTopics = "event_topics"
        case linkedAssets = "linked_assets"
        case linkedCompanies = "linked_companies"
    }
}

struct NewsSentiment: Codable {
    let dominant: String?
    let details: String?
    let panicScore: Double?

    enum CodingKeys: String, CodingKey {
        case dominant, details
        case panicScore = "panic_score"
    }
}

struct HistoryBlock: Codable {
    let count: Int?
    let avgScore: Double?
    let minScore: Int?
    let maxScore: Int?
    let scoreTimeline: [ScorePoint]?
    let actionChanges: [ActionChange]?
    let events: [ActionChange]?
    let priceSeries: [String: [PricePoint]]?

    enum CodingKeys: String, CodingKey {
        case count
        case avgScore = "avg_score"
        case minScore = "min_score"
        case maxScore = "max_score"
        case scoreTimeline = "score_timeline"
        case actionChanges = "action_changes"
        case events
        case priceSeries = "price_series"
    }
}

struct ScorePoint: Codable, Identifiable {
    var id: String { (capturedAt ?? "") + String(score ?? 0) }
    let capturedAt: String?
    let score: Int?
    let action: String?
    let macroAction: String?
    let operationalAction: String?

    enum CodingKeys: String, CodingKey {
        case score, action
        case capturedAt = "captured_at"
        case macroAction = "macro_action"
        case operationalAction = "operational_action"
    }
}

struct ActionChange: Codable, Identifiable {
    var id: String { (capturedAt ?? "") + (from ?? "") + (to ?? "") }
    let capturedAt: String?
    let from: String?
    let to: String?
    let score: Int?

    enum CodingKeys: String, CodingKey {
        case from, to, score
        case capturedAt = "captured_at"
    }
}

struct PricePoint: Codable, Identifiable {
    var id: String { (capturedAt ?? "") + String(value) }
    let capturedAt: String?
    let value: Double
}

struct ComparisonBlock: Codable {
    let hasPrior: Bool?
    let vsPrevious: DiffBlock?
    let vsYesterday: DiffBlock?
    let yesterdayCapturedAt: String?

    enum CodingKeys: String, CodingKey {
        case hasPrior = "has_prior"
        case vsPrevious = "vs_previous"
        case vsYesterday = "vs_yesterday"
        case yesterdayCapturedAt = "yesterday_captured_at"
    }
}

struct DiffBlock: Codable {
    let scoreDelta: Double?
    let actionFrom: String?
    let actionTo: String?
    let actionChanged: Bool?
    let spyPct: Double?
    let gldPct: Double?
    let uupPct: Double?
    let eurusdPct: Double?
    let previousCapturedAt: String?

    enum CodingKeys: String, CodingKey {
        case scoreDelta = "score_delta"
        case actionFrom = "action_from"
        case actionTo = "action_to"
        case actionChanged = "action_changed"
        case spyPct = "spy_pct"
        case gldPct = "gld_pct"
        case uupPct = "uup_pct"
        case eurusdPct = "eurusd_pct"
        case previousCapturedAt = "previous_captured_at"
    }
}

struct PaperBlock: Codable {
    let totalReturnPct: Double?
    let benchmarkReturnPct: Double?
    let alphaVsSpyPct: Double?
    let tradeCount: Int?
    let benchmarkValid: Bool?
    let dataWarnings: [String]?
    let portfolio: PaperPortfolio?
    let trades: [PaperTrade]?
    let riskSummary: PaperRiskSummary?

    enum CodingKeys: String, CodingKey {
        case totalReturnPct = "total_return_pct"
        case benchmarkReturnPct = "benchmark_return_pct"
        case alphaVsSpyPct = "alpha_vs_spy_pct"
        case tradeCount = "trade_count"
        case benchmarkValid = "benchmark_valid"
        case dataWarnings = "data_warnings"
        case portfolio, trades
        case riskSummary = "risk_summary"
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        totalReturnPct = Self.flexDouble(c, .totalReturnPct)
        benchmarkReturnPct = Self.flexDouble(c, .benchmarkReturnPct)
        alphaVsSpyPct = Self.flexDouble(c, .alphaVsSpyPct)
        tradeCount = try c.decodeIfPresent(Int.self, forKey: .tradeCount)
        benchmarkValid = try c.decodeIfPresent(Bool.self, forKey: .benchmarkValid)
        dataWarnings = try c.decodeIfPresent([String].self, forKey: .dataWarnings)
        portfolio = try c.decodeIfPresent(PaperPortfolio.self, forKey: .portfolio)
        trades = try c.decodeIfPresent([PaperTrade].self, forKey: .trades)
        riskSummary = try c.decodeIfPresent(PaperRiskSummary.self, forKey: .riskSummary)
    }

    private static func flexDouble(_ c: KeyedDecodingContainer<CodingKeys>, _ key: CodingKeys) -> Double? {
        if let v = try? c.decode(Double.self, forKey: key) { return v }
        if let s = try? c.decode(String.self, forKey: key), let v = Double(s) { return v }
        if let i = try? c.decode(Int.self, forKey: key) { return Double(i) }
        return nil
    }
}

struct PaperRiskSummary: Codable {
    let maxDrawdownPct: Double?
    let largestExposure: PaperExposure?
    let concentrationHhi: Double?
    let scenarios: [PaperScenario]?
    enum CodingKeys: String, CodingKey {
        case maxDrawdownPct = "max_drawdown_pct"
        case largestExposure = "largest_exposure"
        case concentrationHhi = "concentration_hhi"
        case scenarios
    }
}
struct PaperScenario: Codable, Identifiable {
    var id: String { label ?? UUID().uuidString }
    let label: String?
    let portfolioPct: Double?
    enum CodingKeys: String, CodingKey { case label; case portfolioPct = "portfolio_pct" }
}
struct PaperExposure: Codable { let asset: String?; let weightPct: Double?
    enum CodingKeys: String, CodingKey { case asset; case weightPct = "weight_pct" }
}

struct PaperPortfolio: Codable {
    let cashPct: Double?
    let holdings: [String: Double]?
    let lastAction: String?
    let lastScore: Int?
    let lastUpdate: String?
    let startingValue: Double?
    let currentValue: Double?

    enum CodingKeys: String, CodingKey {
        case holdings
        case cashPct = "cash_pct"
        case lastAction = "last_action"
        case lastScore = "last_score"
        case lastUpdate = "last_update"
        case startingValue = "starting_value"
        case currentValue = "current_value"
    }
}

struct PaperTrade: Codable, Identifiable {
    var id: String { (capturedAt ?? "") + (action ?? "") + String(score ?? 0) }
    let capturedAt: String?
    let action: String?
    let score: Int?
    let allocation: [String: Int]?
    let portfolioValue: Double?
    let benchmarkValue: Double?
    let pnlSinceLastPct: Double?
    let actionChanged: Bool?

    enum CodingKeys: String, CodingKey {
        case action, score, allocation
        case capturedAt = "captured_at"
        case portfolioValue = "portfolio_value"
        case benchmarkValue = "benchmark_value"
        case pnlSinceLastPct = "pnl_since_last_pct"
        case actionChanged = "action_changed"
    }
}

struct TrackRecordBlock: Codable {
    let sampleSize: Int?
    let forwardDays: Int?
    let macroBuyHitRatePct: Double?
    let macroBuyCount: Int?
    let macroBuyAvgReturnPct: Double?
    let defensiveHitRatePct: Double?
    let defensiveCount: Int?
    let defensiveAvgReturnPct: Double?
    let message: String?

    enum CodingKeys: String, CodingKey {
        case message
        case sampleSize = "sample_size"
        case forwardDays = "forward_days"
        case macroBuyHitRatePct = "macro_buy_hit_rate_pct"
        case macroBuyCount = "macro_buy_count"
        case macroBuyAvgReturnPct = "macro_buy_avg_return_pct"
        case defensiveHitRatePct = "defensive_hit_rate_pct"
        case defensiveCount = "defensive_count"
        case defensiveAvgReturnPct = "defensive_avg_return_pct"
    }
}
