import Foundation

enum NativeSnapshotContractChecks {
    private struct CheckFailure: LocalizedError {
        let message: String
        var errorDescription: String? { message }
    }

    static func run(fixturePath: String) throws {
        let fixture = try Data(contentsOf: URL(fileURLWithPath: fixturePath))
        let root = try object(JSONSerialization.jsonObject(with: fixture))
        let snapshot = try NexusAPIClient.decodeNativeSnapshot(fixture)
        try expect(snapshot.schema == "nexus.native.v1", "schema")
        try expect(snapshot.capturedAtUtc == "2026-01-08T14:00:00+00:00", "captured_at_utc")
        try expect(snapshot.status == "BLOCKED" && snapshot.statusChip?.macroBlock == true, "status_chip")
        try expect(snapshot.blockBanner?.countdownSeconds == 7_200, "block_banner.countdown_seconds")
        try expect(snapshot.calendar?.shouldBlock == true, "calendar.should_block")
        try expect(snapshot.sessionPlan?.allowsEntry == false, "session_plan.allows_entry")
        try expect(snapshot.decision?.operationalAction == "ESPERAR" && snapshot.decision?.score == 58, "decision")
        try expect(snapshot.settings?.refreshIntervalSeconds == 600 && snapshot.watchlist == ["SPY", "GLD"], "settings / watchlist")
        try expect(snapshot.freshness?.layers?.first(where: { $0.key == "market" })?.ageSeconds == 15, "freshness.layers")
        try expect(snapshot.assets?["SPY"]?.price == 123.45 && snapshot.sparklines?["SPY"]?.first?.value == 123.45, "assets / sparklines")
        try expect(snapshot.rotation?.themes?.first?.companies?.first?.ticker == "TEST", "rotation.themes.companies")
        try expect(snapshot.gold?.demand?.official?.reserves?.first?.tonnes == 12.5, "gold.demand.official.reserves")
        try expect(snapshot.news?.items?.count == 2 && snapshot.forex?.headlines?.count == 2, "news.items / forex.headlines")

        let news = try object(root["news"])
        let titles = snapshot.news?.items?.map(\.title)
        let rows = try array(news["items"])
        let partial = try mutate(root, ["news", "items"], [[:], rows[0], NSNull(), 17, rows[1]])
        let decodedPartial = try NexusAPIClient.decodeNativeSnapshot(partial)
        try expect(decodedPartial.news?.items?.map(\.title) == titles, "titulares válidos tras tres filas inválidas")
        try expect(decodedPartial.decision?.score == 58 && decodedPartial.sessionPlan?.allowsEntry == false, "se conserva la lectura operativa")

        let forex = try object(root["forex"])
        let headlines = try array(forex["headlines"])
        let partialFX = try NexusAPIClient.decodeNativeSnapshot(mutate(root, ["forex", "headlines"], [[:]] + headlines))
        try expect(partialFX.forex?.headlines?.count == headlines.count, "forex.headlines recupera filas")

        let history = try object(root["history"])
        let prices = try object(history["price_series"])
        let spy = try array(prices["SPY"])
        let partialHistory = try NexusAPIClient.decodeNativeSnapshot(
            mutate(root, ["history", "price_series", "SPY"], [[:]] + spy)
        )
        try expect(partialHistory.history?.priceSeries?["SPY"]?.count == spy.count, "se descarta solo el precio malformado")
        try expect(partialHistory.history?.priceSeries?["SPY"]?.last?.value == 123.45, "history.price_series recupera filas")
        try expect(partialHistory.history?.priceSeries?["SPY"]?.last?.capturedAt == snapshot.capturedAtUtc, "price_series.*.captured_at")

        let official = try object(try object(try object(root["gold"])["demand"])["official"])
        let reserves = try array(official["reserves"])
        let partialGold = try NexusAPIClient.decodeNativeSnapshot(
            mutate(root, ["gold", "demand", "official", "reserves"], [["tonnes": 99]] + reserves)
        )
        try expect(partialGold.gold?.demand?.official?.reserves?.map(\.id) == ["fixture-reserve"], "reserva sin identificador descartada")

        let themes = try array(try object(root["rotation"])["themes"])
        var theme = try object(themes.first)
        theme["companies"] = [["price": "inválido"]] + (try array(theme["companies"]))
        let partialRotation = try NexusAPIClient.decodeNativeSnapshot(
            mutate(root, ["rotation", "themes"], [["score": "inválido"], theme])
        )
        try expect(partialRotation.rotation?.themes?.count == 1, "tema inválido descartado")
        try expect(partialRotation.rotation?.themes?.first?.companies?.map(\.ticker) == ["TEST"], "empresa inválida descartada")

        let noNews = try NexusAPIClient.decodeNativeSnapshot(mutate(root, ["news", "items"], nil))
        try expect(noNews.news?.items == nil, "lista opcional ausente")
        let emptyNews = try NexusAPIClient.decodeNativeSnapshot(mutate(root, ["news", "items"], [] as [Any]))
        try expect(emptyNews.news?.items?.isEmpty == true, "lista vacía explícita")
        try expectRejected(mutate(root, ["news", "items"], "no es una lista"), mentions: "news.items")
        try expectRejected(mutate(root, ["schema"], "nexus.native.incompatible"), mentions: "schema")
        try expectRejected(mutate(root, ["captured_at_utc"], "sin fecha"), mentions: "captured_at_utc")
        try expectRejected(mutate(root, ["session_plan", "allows_entry"], nil), mentions: "allows_entry")
        try expectRejected(mutate(root, ["session_plan", "allows_entry"], "true"), mentions: "allows_entry")
        try expectRejected(mutate(root, ["session_plan", "allows_entry"], true), mentions: "allows_entry")
        try expectRejected(mutate(root, ["decision", "operational_action"], nil), mentions: "operational_action")
        try expectRejected(mutate(root, ["calendar", "should_block"], NSNull()), mentions: "should_block")
        try expectRejected(mutate(root, ["block_banner"], NSNull()), mentions: "block_banner")
        try expectRejected(mutate(root, ["block_banner", "title"], nil), mentions: "block_banner")

        var unblocked = root
        unblocked["status"] = "HEALTHY"
        unblocked["block_banner"] = NSNull()
        unblocked["calendar"] = ["should_block": false]
        unblocked["decision"] = ["operational_action": "COMPRAR"]
        unblocked["session_plan"] = ["allows_entry": true]
        let allowed = try NexusAPIClient.decodeNativeSnapshot(JSONSerialization.data(withJSONObject: unblocked))
        try expect(allowed.sessionPlan?.allowsEntry == true && allowed.blockBanner == nil, "permiso válido sin bloqueo")
        print("Contrato nativo: fixture Python, filas inválidas aisladas y datos operativos estrictos")
    }

    private static func expect(_ condition: @autoclosure () -> Bool, _ description: String) throws {
        guard condition() else { throw CheckFailure(message: "Falló la comprobación: \(description)") }
    }

    private static func expectRejected(_ data: Data, mentions field: String) throws {
        do {
            _ = try NexusAPIClient.decodeNativeSnapshot(data)
        } catch let error as NexusAPIError {
            try expect(error.localizedDescription.contains(field), "diagnóstico para \(field): \(error.localizedDescription)")
            return
        }
        throw CheckFailure(message: "La respuesta inválida pasó el control: \(field)")
    }

    private static func object(_ value: Any?) throws -> [String: Any] {
        guard let result = value as? [String: Any] else { throw CheckFailure(message: "Se esperaba un objeto JSON en el fixture") }
        return result
    }

    private static func array(_ value: Any?) throws -> [Any] {
        guard let result = value as? [Any] else { throw CheckFailure(message: "Se esperaba una lista JSON en el fixture") }
        return result
    }

    private static func mutate(_ root: [String: Any], _ path: [String], _ value: Any?) throws -> Data {
        func update(_ object: [String: Any], at path: ArraySlice<String>) throws -> [String: Any] {
            var result = object
            guard let key = path.first else { throw CheckFailure(message: "Ruta JSON vacía") }
            if path.count == 1 {
                result[key] = value
            } else {
                result[key] = try update(Self.object(result[key]), at: path.dropFirst())
            }
            return result
        }
        return try JSONSerialization.data(withJSONObject: update(root, at: path[...]))
    }
}
