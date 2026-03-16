тыimport SwiftUI
import WebKit

struct WebView: UIViewRepresentable {
    let url: URL

    func makeUIView(context: Context) -> WKWebView {
        let webView = WKWebView()
        webView.scrollView.bounces = false
        webView.allowsBackForwardNavigationGestures = false
        webView.load(URLRequest(url: url))
        return webView
    }

    func updateUIView(_ webView: WKWebView, context: Context) {
        

        guard webView.url != url else { return }
        webView.load(URLRequest(url: url))
    }
}

struct ContentView: View {
    private let siteURL = URL(string: "https://turizm03.ru/")

    var body: some View {
        Group {
            if let siteURL {
                WebView(url: siteURL)
            } else {
                ContentUnavailableView("Invalid URL", systemImage: "exclamationmark.triangle")
            }
        }
        .ignoresSafeArea()
    }
}

#Preview {
    ContentView()
}
