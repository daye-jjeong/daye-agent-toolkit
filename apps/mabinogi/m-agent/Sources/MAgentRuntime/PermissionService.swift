import ApplicationServices
@preconcurrency import CoreGraphics
import Foundation

public enum PermissionCapability: CaseIterable, Equatable, Sendable {
    case screenRecording
    case accessibility
    case inputMonitoring
}

public enum PermissionAuthorizationStatus: Equatable, Sendable {
    case authorized
    case denied
}

public protocol PermissionChecking: Sendable {
    func status(
        for capability: PermissionCapability
    ) async -> PermissionAuthorizationStatus

    func requestAuthorization(
        for capability: PermissionCapability
    ) async -> PermissionAuthorizationStatus
}

public struct PermissionService: PermissionChecking, Sendable {
    public init() {}

    public func status(
        for capability: PermissionCapability
    ) async -> PermissionAuthorizationStatus {
        isAuthorized(capability) ? .authorized : .denied
    }

    public func requestAuthorization(
        for capability: PermissionCapability
    ) async -> PermissionAuthorizationStatus {
        let authorized: Bool
        switch capability {
        case .screenRecording:
            authorized = CGRequestScreenCaptureAccess()
        case .accessibility:
            let options = [
                "AXTrustedCheckOptionPrompt": true,
            ] as CFDictionary
            authorized = AXIsProcessTrustedWithOptions(options)
        case .inputMonitoring:
            authorized = CGRequestListenEventAccess()
        }
        return authorized ? .authorized : .denied
    }

    private func isAuthorized(
        _ capability: PermissionCapability
    ) -> Bool {
        switch capability {
        case .screenRecording:
            CGPreflightScreenCaptureAccess()
        case .accessibility:
            AXIsProcessTrusted()
        case .inputMonitoring:
            CGPreflightListenEventAccess()
        }
    }
}
