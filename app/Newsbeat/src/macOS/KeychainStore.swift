import Foundation
import Security

enum KeychainStore {
    private static let service = "ee.risto.newsbeat"
    private static let account = "ANTHROPIC_API_KEY"

    static func readAPIKey() -> String {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]
        var result: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &result) == errSecSuccess,
              let data = result as? Data,
              let value = String(data: data, encoding: .utf8)
        else {
            return ""
        }
        return value
    }

    static func saveAPIKey(_ value: String) throws {
        let identity: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ]

        if value.isEmpty {
            SecItemDelete(identity as CFDictionary)
            return
        }

        let data = Data(value.utf8)
        let update: [String: Any] = [
            kSecValueData as String: data,
        ]
        let status = SecItemUpdate(
            identity as CFDictionary,
            update as CFDictionary
        )
        if status == errSecItemNotFound {
            var insertion = identity
            insertion[kSecValueData as String] = data
            let insertStatus = SecItemAdd(insertion as CFDictionary, nil)
            guard insertStatus == errSecSuccess else {
                throw KeychainError.status(insertStatus)
            }
        } else if status != errSecSuccess {
            throw KeychainError.status(status)
        }
    }
}

enum KeychainError: LocalizedError {
    case status(OSStatus)

    var errorDescription: String? {
        switch self {
        case let .status(status):
            "Keychain operation failed with status \(status)."
        }
    }
}
