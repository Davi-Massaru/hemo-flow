package com.hemoflow.pex;

import com.intersystems.enslib.pex.BusinessOperation;
import com.intersystems.jdbc.IRISObject;
import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.*;
import java.util.UUID;

/** Materializes an approved plan only; selection and approval stay outside Java. */
public class CampaignCreationOperation extends BusinessOperation {
    private final ObjectMapper mapper=new ObjectMapper();
    public void OnInit() { }
    public void OnTearDown() { }
    public Object OnMessage(Object message) throws Exception {
        IRISObject req=(IRISObject)message;
        JsonNode plan=mapper.readTree(req.getString("JSON"));
        if (!plan.path("approved").asBoolean(false)) throw new SecurityException("Plan not approved");
        ArrayNode invitations=mapper.createArrayNode();
        for (JsonNode recipient:plan.withArray("recipients")) {
            if (recipient.path("type").asText().equals("DONOR") && !recipient.path("opt_in").asBoolean(false))
                throw new SecurityException("Donor lacks opt-in");
            ObjectNode item=mapper.createObjectNode();
            String stable=plan.get("campaign_id").asText()+":"+recipient.get("id").asText();
            item.put("id",UUID.nameUUIDFromBytes(stable.getBytes(java.nio.charset.StandardCharsets.UTF_8)).toString());
            item.put("recipient_id",recipient.get("id").asText());
            item.put("recipient_type",recipient.get("type").asText());
            item.put("campaign_id",plan.get("campaign_id").asText());
            invitations.add(item);
        }
        ObjectNode result=mapper.createObjectNode().put("creator","JAVA_PEX"); result.set("invitations",invitations);
        IRISObject response=(IRISObject)req.iris.classMethodObject("HemoFlow.Response","%New");
        response.set("JSON",result.toString()); return response;
    }
}
