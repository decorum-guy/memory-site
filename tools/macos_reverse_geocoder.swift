import CoreLocation
import Foundation

private struct GeocodeRequest: Decodable {
    let key: String
    let latitude: Double
    let longitude: Double
}

private struct GeocodeResponse: Encodable {
    let key: String
    let latitude: Double
    let longitude: Double
    let name: String?
    let locality: String?
    let subLocality: String?
    let administrativeArea: String?
    let subAdministrativeArea: String?
    let country: String?
    let isoCountryCode: String?
    let thoroughfare: String?
    let subThoroughfare: String?
    let ocean: String?
    let inlandWater: String?
    let areasOfInterest: [String]
    let error: String?
}

private func isRetryableNetworkError(_ error: Error) -> Bool {
    let value = error as NSError
    return value.domain == kCLErrorDomain && value.code == CLError.Code.network.rawValue
}

private func geocodeWithBackoff(
    _ request: GeocodeRequest,
    locale: Locale
) async throws -> CLPlacemark? {
    let location = CLLocation(latitude: request.latitude, longitude: request.longitude)
    let retryDelays: [UInt64] = [2, 6, 15]
    var lastError: Error?

    for attempt in 0...retryDelays.count {
        do {
            return try await CLGeocoder()
                .reverseGeocodeLocation(location, preferredLocale: locale)
                .first
        } catch {
            lastError = error
            guard isRetryableNetworkError(error), attempt < retryDelays.count else {
                throw error
            }
            let delay = retryDelays[attempt]
            try? await Task.sleep(nanoseconds: delay * 1_000_000_000)
        }
    }

    throw lastError ?? NSError(
        domain: kCLErrorDomain,
        code: CLError.Code.network.rawValue,
        userInfo: [NSLocalizedDescriptionKey: "Не удалось выполнить геокодирование"]
    )
}

private func runGeocoder() async {
    let decoder = JSONDecoder()
    let encoder = JSONEncoder()
    encoder.outputFormatting = [.withoutEscapingSlashes]
    let locale = Locale(identifier: "ru_RU")

    while let line = readLine() {
        guard let data = line.data(using: .utf8) else { continue }
        let response: GeocodeResponse

        do {
            let request = try decoder.decode(GeocodeRequest.self, from: data)
            let placemark = try await geocodeWithBackoff(request, locale: locale)
            response = GeocodeResponse(
                key: request.key,
                latitude: request.latitude,
                longitude: request.longitude,
                name: placemark?.name,
                locality: placemark?.locality,
                subLocality: placemark?.subLocality,
                administrativeArea: placemark?.administrativeArea,
                subAdministrativeArea: placemark?.subAdministrativeArea,
                country: placemark?.country,
                isoCountryCode: placemark?.isoCountryCode,
                thoroughfare: placemark?.thoroughfare,
                subThoroughfare: placemark?.subThoroughfare,
                ocean: placemark?.ocean,
                inlandWater: placemark?.inlandWater,
                areasOfInterest: placemark?.areasOfInterest ?? [],
                error: nil
            )
        } catch {
            let fallback = try? decoder.decode(GeocodeRequest.self, from: data)
            response = GeocodeResponse(
                key: fallback?.key ?? "",
                latitude: fallback?.latitude ?? 0,
                longitude: fallback?.longitude ?? 0,
                name: nil,
                locality: nil,
                subLocality: nil,
                administrativeArea: nil,
                subAdministrativeArea: nil,
                country: nil,
                isoCountryCode: nil,
                thoroughfare: nil,
                subThoroughfare: nil,
                ocean: nil,
                inlandWater: nil,
                areasOfInterest: [],
                error: String(describing: error)
            )
        }

        if let encoded = try? encoder.encode(response),
           let text = String(data: encoded, encoding: .utf8) {
            print(text)
            fflush(stdout)
        }

        // Apple rate-limits geocoding. Keep requests sequential and gentle;
        // retryable network/rate-limit errors are additionally backed off above.
        try? await Task.sleep(nanoseconds: 1_500_000_000)
    }
}

Task {
    await runGeocoder()
    exit(EXIT_SUCCESS)
}
dispatchMain()
