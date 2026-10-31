package com.hemoflow.pex;

import com.intersystems.enslib.pex.BusinessOperation;
import com.intersystems.jdbc.IRISObject;
import com.fasterxml.jackson.databind.*;

public class FederatedInventoryOperation extends BusinessOperation {
    private final ObjectMapper mapper=new ObjectMapper();
    public String getAdapterType() { return "com.hemoflow.pex.FederatedInventoryAdapter"; }
    public void OnInit() { }
    public void OnTearDown() { }
    public Object OnMessage(Object message) throws Exception {
        IRISObject req=(IRISObject)message;
        JsonNode input=mapper.readTree(req.getString("JSON"));
        String result=(String)Adapter.invoke("Query",input.get("endpoint").asText(),input.get("body").toString());
        IRISObject response=(IRISObject)req.iris.classMethodObject("HemoFlow.Response","%New");
        response.set("JSON",result);
        return response;
    }
}
