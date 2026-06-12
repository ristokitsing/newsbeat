import UIKit

enum PlatformActions {
    static func copy(_ value: String) {
        UIPasteboard.general.string = value
    }
}

