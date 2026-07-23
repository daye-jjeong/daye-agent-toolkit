@preconcurrency import CoreGraphics

public enum ObservationGeometry {
    public static func topLeftPixelRect(
        fromVisionNormalizedRect rect: CGRect,
        imageSize: CGSize
    ) -> CGRect? {
        guard
            isValid(imageSize),
            isFinite(rect),
            rect.size.width > 0,
            rect.size.height > 0
        else {
            return nil
        }

        let rawMaxX = rect.origin.x + rect.size.width
        let rawMaxY = rect.origin.y + rect.size.height
        guard rawMaxX.isFinite, rawMaxY.isFinite else {
            return nil
        }

        let minX = max(0, rect.origin.x)
        let minY = max(0, rect.origin.y)
        let maxX = min(1, rawMaxX)
        let maxY = min(1, rawMaxY)
        guard minX < maxX, minY < maxY else {
            return nil
        }

        return CGRect(
            x: minX * imageSize.width,
            y: (1 - maxY) * imageSize.height,
            width: (maxX - minX) * imageSize.width,
            height: (maxY - minY) * imageSize.height
        )
    }
}

private extension ObservationGeometry {
    static func isValid(_ imageSize: CGSize) -> Bool {
        imageSize.width.isFinite
            && imageSize.height.isFinite
            && imageSize.width > 0
            && imageSize.height > 0
    }

    static func isFinite(_ rect: CGRect) -> Bool {
        rect.origin.x.isFinite
            && rect.origin.y.isFinite
            && rect.size.width.isFinite
            && rect.size.height.isFinite
    }
}
