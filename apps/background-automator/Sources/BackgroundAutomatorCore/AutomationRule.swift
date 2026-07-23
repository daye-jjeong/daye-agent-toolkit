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

public struct AutomationRule: Codable, Equatable, Sendable {
    public let id: String
    public let requiredTexts: [String]
    public let forbiddenTexts: [String]
    public let action: AutomationAction
    public let regions: LayoutRegionMap
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
        self.minimumOCRConfidence = minimumOCRConfidence
        self.stableObservationCount = stableObservationCount
        self.postActionDelaySeconds = postActionDelaySeconds
        self.cooldownSeconds = cooldownSeconds
    }
}
