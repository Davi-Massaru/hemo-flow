package com.hemoflow.pex;

import com.intersystems.enslib.pex.OutboundAdapter;
import java.net.URI;
import java.net.http.*;
import java.time.Duration;
import java.nio.file.*;
import java.util.Properties;

/** Custom outbound adapter, compiled against the jar shipped in EAP build 154. */
public class FederatedInventoryAdapter extends OutboundAdapter {
    private HttpClient client;
    public void OnInit() { client=HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(3)).build(); }
    public void OnTearDown() { }
    public String Query(String endpoint,String payload) throws Exception {
        URI uri=URI.create(endpoint);
        Properties config=new Properties();
        try (var in=Files.newInputStream(Path.of("/opt/hemoflow/.env"))) { config.load(in); }
        String demo=System.getenv().getOrDefault("HEMOFLOW_DEMO",config.getProperty("HEMOFLOW_DEMO","0"));
        if (!"https".equals(uri.getScheme()) && !("1".equals(demo) && "http".equals(uri.getScheme()) &&
                java.util.Set.of("center-a","center-b","center-c","localhost","127.0.0.1").contains(uri.getHost())))
            throw new SecurityException("Endpoint transport not allowed");
        String token=System.getenv().getOrDefault("HEMOFLOW_CENTER_TOKEN",config.getProperty("HEMOFLOW_CENTER_TOKEN",""));
        if (token.isBlank()) throw new SecurityException("Missing center credential");
        HttpRequest req=HttpRequest.newBuilder(uri).timeout(Duration.ofSeconds(5))
            .header("Content-Type","application/fhir+json").header("Authorization","Bearer "+token)
            .POST(HttpRequest.BodyPublishers.ofString(payload)).build();
        HttpResponse<java.io.InputStream> response=client.send(req,HttpResponse.BodyHandlers.ofInputStream());
        try (var body=response.body()) {
            byte[] bytes=body.readNBytes(65537);
            if (response.statusCode()!=200 || bytes.length>65536) throw new IllegalStateException("Inventory unavailable: HTTP "+response.statusCode());
            return new String(bytes,java.nio.charset.StandardCharsets.UTF_8);
        }
    }
}
