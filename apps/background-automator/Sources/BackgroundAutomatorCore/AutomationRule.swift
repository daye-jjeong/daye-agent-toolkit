public struct AutomationAction: Codable, Equatable, Sendable {
    public let targetText: String?
    public let safePointRegion: NormalizedRegion?
    /// 글자 끝말로 누를 대상을 찾는다.
    ///
    /// 기본은 완전 일치다 — 그 엄격함이 '10 입장하기'를 눌러 은동전을
    /// 몰래 쓰는 일을 막는다. 사용자가 은동전 사용을 켠 규칙에서만,
    /// OCR이 ') 입장하기'처럼 앞을 흘려 읽어도 잡도록 끝말을 쓴다.
    public let targetTextSuffix: String?

    public init(
        targetText: String?,
        safePointRegion: NormalizedRegion?,
        targetTextSuffix: String? = nil
    ) {
        self.targetText = targetText
        self.safePointRegion = safePointRegion
        self.targetTextSuffix = targetTextSuffix
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
