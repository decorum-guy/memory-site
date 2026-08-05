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

@main
private struct MemoryReverseGeocoder {
    static func main() async {
        let decoder = JSONDecoder()
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.withoutEscapingSlashes]
        let locale = Locale(identifier: "ru_RU")

        while let line = readLine() {
            guard let data = line.data(using: .utf8) else { continue }
            let response: GeocodeResponse

            do {
                let request = try decoder.decode(GeocodeRequest.self, from: data)
                let location = CLLocation(latitude: request.latitude, longitude: request.longitude)
                let placemarks = try await CLGeocoder().reverseGeocodeLocation(location, preferredLocale: locale)
                let placemark = placemarks.first
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
                let fallback = (try? decoder.decode(GeocodeRequest.self, from: data))
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

            if let encoded = try? encoder.encode(response), let text = String(data: encoded, encoding: .utf8) {
                print(text)
                fflush(stdout)
            }

            // Apple rate-limits geocoding. Keep requests deliberately sequential and gentle.
            try? await Task.sleep(nanoseconds: 400_000_000)
        }
    }
}
