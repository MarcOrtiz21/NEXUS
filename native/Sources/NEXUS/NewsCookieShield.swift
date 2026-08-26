import Foundation
import WebKit

enum NewsCookieShield {
    static let defaultsKey = "newsBlockCookieBanners"
    private static let legacyRuleListIDs = ["nexus-cookie-shield-v1"]

    static var isEnabled: Bool {
        get { UserDefaults.standard.object(forKey: defaultsKey) as? Bool ?? true }
        set { UserDefaults.standard.set(newValue, forKey: defaultsKey) }
    }

    static func installUserScript(on controller: WKUserContentController) {
        controller.removeAllUserScripts()
        let script = WKUserScript(source: userScript, injectionTime: .atDocumentStart, forMainFrameOnly: false)
        controller.addUserScript(script)
    }

    static func clearLegacyRules(from controller: WKUserContentController) {
        controller.removeAllContentRuleLists()
        for identifier in legacyRuleListIDs {
            WKContentRuleListStore.default()?.removeContentRuleList(forIdentifier: identifier) { _ in }
        }
    }

    /// Auto-clicks Reject/Essential and hides leftover cookie overlays.
    /// Does not block scripts: Yahoo and The Guardian refuse to render if the CMP is blocked.
    static let userScript = """
    (() => {
      if (window.__nexusCookieShield) return;
      window.__nexusCookieShield = true;

      const host = location.hostname;
      const fullPageConsent = /(^|\\.)((consent|guce)\\.(google|yahoo|youtube)|consent\\.cmp\\.oath)\\./i.test(host)
        || /consent\\.(google|yahoo)/i.test(host)
        || host.indexOf('guce.yahoo') !== -1
        || host.indexOf('consent.yahoo') !== -1
        || host.indexOf('consent.google') !== -1
        || host.indexOf('consent.cmp.oath') !== -1;
      const isGuardian = /(^|\\.)theguardian\\.com$/i.test(host);
      const isYahoo = /(^|\\.)(yahoo|yimg)\\./i.test(host) || host.indexOf('oath.com') !== -1;

      const HIDE = [
        '#onetrust-banner-sdk', '#onetrust-consent-sdk', '#onetrust-pc-sdk',
        '.onetrust-pc-dark-filter', '#didomi-host', '#didomi-popup',
        '.didomi-popup-container', '#qc-cmp2-container', '.qc-cmp2-container',
        '.cky-consent-container', '.cky-overlay', '#CybotCookiebotDialog',
        '#CybotCookiebotDialogBodyUnderlay', '#cookieConsent', '.ecb-cookieConsent',
        '#ecb-cookieConsent', '#cookie-law-info-bar', '.cc-window', '.cc-overlay',
        '#usercentrics-root', '.fc-consent-root', '.fc-dialog-overlay'
      ];
      const REJECT_RE = /(reject all|reject optional|decline all|necessary only|essential only|solo esenciales|solo necesarias|solo las necesarias|rechazar todo|rechazar todas|rechazar|no aceptar|refuser tout|alle ablehnen|nur notwendige|reject cookies|decline cookies|continue without|no, thank you|i do not agree|see ads that are less)/i;
      const ACCEPT_RE = /(accept all|aceptar todo|agree|i agree|allow all|acepto|yes, i.?m happy|pause ad-?blocker|allow ads|support us|subscribe)/i;
      let rejected = false;

      const hide = () => {
        if (fullPageConsent || isYahoo || isGuardian) return;
        for (const sel of HIDE) {
          document.querySelectorAll(sel).forEach((el) => {
            el.style.setProperty('display', 'none', 'important');
            el.style.setProperty('visibility', 'hidden', 'important');
            el.style.setProperty('pointer-events', 'none', 'important');
          });
        }
        if (document.body) {
          document.body.style.removeProperty('overflow');
          document.body.classList.remove('sp-message-open', 'overflow-hidden', 'didomi-popup-open');
        }
      };

      const clickReject = () => {
        if (rejected) return false;
        const named = [
          'onetrust-reject-all-handler',
          'onetrust-reject-all-button',
          'cky-btn-reject'
        ];
        for (const id of named) {
          const el = document.getElementById(id) || document.querySelector('.' + id);
          if (el) { el.click(); rejected = true; return true; }
        }
        const nodes = document.querySelectorAll('button, a, [role="button"], input[type="button"], input[type="submit"]');
        for (const node of nodes) {
          const label = ((node.innerText || node.value || node.getAttribute('aria-label') || '') + '').trim();
          if (!label || ACCEPT_RE.test(label)) continue;
          if (REJECT_RE.test(label)) {
            node.click();
            rejected = true;
            return true;
          }
        }
        return false;
      };

      const run = () => { clickReject(); hide(); };
      run();
      document.addEventListener('DOMContentLoaded', run);
      const obs = new MutationObserver(() => run());
      obs.observe(document.documentElement, { childList: true, subtree: true });
    })();
    """
}
