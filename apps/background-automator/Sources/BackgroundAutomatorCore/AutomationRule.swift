public struct AutomationAction: Codable, Equatable, Sendable {
    public let targetText: String?
    public let safePointRegion: NormalizedRegion?

    public init(
        targetText: String?,
        safePointRegion: NormalizedRegion?
    ) {
        self.targetText = targetText
        self.safePointRegion = safePointRegion
    }
}

public struct AppearanceRange: Codable, Equatable, Sendable {
    public let minimumSaturation: Double
    public let maximumSaturation: Double
    public let minimumLuminance: Double
    public let maximumLuminance: Double

    public init(
        minimumSaturation: Double,
        maximumSaturation: Double,
        minimumLuminance: Double,
        maximumLuminance: Double
    ) {
        self.minimumSaturation = minimumSaturation
        self.maximumSaturation = maximumSaturation
        self.minimumLuminance = minimumLuminance
        self.maximumLuminance = maximumLuminance
    }

    public func contains(
        saturation: Double,
        luminance: Double
    ) -> Bool {
        saturation >= minimumSaturation
            && saturation <= maximumSaturation
            && luminance >= minimumLuminance
            && luminance <= maximumLuminance
    }
}

public struct AutomationAppearanceConstraint:
    Codable,
    Equatable,
    Sendable
{
    public let contextText: String
    public let contextRegions: LayoutRegionMap
    public let contextRange: AppearanceRange
    public let targetRange: AppearanceRange

    public init(
        contextText: String,
        contextRegions: LayoutRegionMap,
        contextRange: AppearanceRange,
        targetRange: AppearanceRange
    ) {
        self.contextText = contextText
        self.contextRegions = contextRegions
        self.contextRange = contextRange
        self.targetRange = targetRange
    }
}

public struct AutomationRule: Codable, Equatable, Sendable {
    public let id: String
    public let requiredTexts: [String]
    public let forbiddenTexts: [String]
    public let action: AutomationAction
    public let regions: LayoutRegionMap
    public let appearance: AutomationAppearanceConstraint?
    public let minimumOCRConfidence: Double
    public let stableObservationCount: Int
    public let postActionDelaySeconds: Double
    public let cooldownSeconds: Double

    public init(
        id: String,
        requiredTexts: [String],
        forbiddenTexts: [String],
        action: AutomationAction,
        regions: LayoutRegionMap,
        appearance: AutomationAppearanceConstraint? = nil,
        minimumOCRConfidence: Double,
        stableObservationCount: Int,
        postActionDelaySeconds: Double,
        cooldownSeconds: Double
    ) {
        self.id = id
        self.requiredTexts = requiredTexts
        self.forbiddenTexts = forbiddenTexts
        self.action = action
        self.regions = regions
        self.appearance = appearance
        self.minimumOCRConfidence = minimumOCRConfidence
        self.stableObservationCount = stableObservationCount
        self.postActionDelaySeconds = postActionDelaySeconds
        self.cooldownSeconds = cooldownSeconds
    }
}
