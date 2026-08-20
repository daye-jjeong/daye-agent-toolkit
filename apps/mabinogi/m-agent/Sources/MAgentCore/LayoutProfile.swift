public enum LayoutProfile: String, Codable, Equatable, Sendable {
    case landscape
    case portraitMobile = "portrait-mobile"
    case unsupported
}

public struct NormalizedRegion: Codable, Equatable, Sendable {
    public let minX: Double
    public let minY: Double
    public let maxX: Double
    public let maxY: Double

    public init(
        minX: Double,
        minY: Double,
        maxX: Double,
        maxY: Double
    ) {
        self.minX = minX
        self.minY = minY
        self.maxX = maxX
        self.maxY = maxY
    }
}

public struct LayoutRegionMap: Codable, Equatable, Sendable {
    private let storage: [LayoutProfile: NormalizedRegion]

    public init(_ storage: [LayoutProfile: NormalizedRegion]) {
        self.storage = storage
    }

    public subscript(layout: LayoutProfile) -> NormalizedRegion? {
        storage[layout]
    }

    public var entries: [LayoutProfile: NormalizedRegion] {
        storage
    }

    public init(from decoder: any Decoder) throws {
        let container = try decoder.container(keyedBy: LayoutRegionCodingKey.self)
        var decoded: [LayoutProfile: NormalizedRegion] = [:]

        for key in container.allKeys {
            guard let layout = LayoutProfile(rawValue: key.stringValue) else {
                throw DecodingError.dataCorruptedError(
                    forKey: key,
                    in: container,
                    debugDescription: "Unknown layout profile: \(key.stringValue)"
                )
            }
            decoded[layout] = try container.decode(
                NormalizedRegion.self,
                forKey: key
            )
        }

        storage = decoded
    }

    public func encode(to encoder: any Encoder) throws {
        var container = encoder.container(keyedBy: LayoutRegionCodingKey.self)

        for (layout, region) in storage {
            try container.encode(
                region,
                forKey: LayoutRegionCodingKey(layout.rawValue)
            )
        }
    }
}

private struct LayoutRegionCodingKey: CodingKey {
    let stringValue: String
    let intValue: Int? = nil

    init(_ stringValue: String) {
        self.stringValue = stringValue
    }

    init?(stringValue: String) {
        self.init(stringValue)
    }

    init?(intValue: Int) {
        nil
    }
}
