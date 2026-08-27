import Foundation
import SwiftUI

enum AppLanguage: String, CaseIterable, Identifiable {
    case spanish = "es"
    case english = "en"

    var id: String { rawValue }
    var locale: Locale { Locale(identifier: rawValue) }
    var displayName: String {
        switch self {
        case .spanish: return "Español"
        case .english: return "English"
        }
    }
}

enum L10n {
    static func string(_ key: String, language: AppLanguage) -> String {
        guard
            let path = Bundle.main.path(forResource: language.rawValue, ofType: "lproj"),
            let bundle = Bundle(path: path)
        else {
            return key
        }
        return bundle.localizedString(forKey: key, value: key, table: nil)
    }
}

private struct AppLanguageKey: EnvironmentKey {
    static let defaultValue = AppLanguage.spanish
}

extension EnvironmentValues {
    var appLanguage: AppLanguage {
        get { self[AppLanguageKey.self] }
        set { self[AppLanguageKey.self] = newValue }
    }
}

extension View {
    func nexusLanguage(_ language: AppLanguage) -> some View {
        environment(\.appLanguage, language)
            .environment(\.locale, language.locale)
    }
}
