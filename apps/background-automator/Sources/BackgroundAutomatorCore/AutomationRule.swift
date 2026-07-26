public struct AutomationAction: Codable, Equatable, Sendable {
    public let targetText: String?
    public let safePointRegion: NormalizedRegion?
    /// 글자 끝말로 누를 대상을 찾는다.
    ///
    /// 기본은 완전 일치다 — 그 엄격함이 '10 입장하기'를 눌러 은동전을
    /// 몰래 쓰는 일을 막는다. 사용자가 은동전 사용을 켠 규칙에서만,
    /// OCR이 ') 입장하기'처럼 앞을 흘려 읽어도 잡도록 끝말을 쓴다.
    public let targetTextSuffix: String?
    /// 같은 글자가 화면에 여러 번 뜰 때, 이 글자보다 아래에 있는 것만
    /// 대상으로 삼는다.
    ///
    /// 던전 입장 화면엔 '선택됨'이 둘이다 — 위는 임무, 아래는 더블 루팅.
    /// 좌표로 가르면 창 비율이 바뀔 때 깨지므로, 카드 안에 늘 있는 안내문을
    /// 기준선으로 쓴다. 세로로 쌓인 카드라 위아래 순서는 비율과 무관하다.
    public let targetBelowText: String?

    public init(
        targetText: String?,
        safePointRegion: NormalizedRegion?,
        targetTextSuffix: String? = nil,
        targetBelowText: String? = nil
    ) {
        self.targetText = targetText
        self.safePointRegion = safePointRegion
        self.targetTextSuffix = targetTextSuffix
        self.targetBelowText = targetBelowText
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
