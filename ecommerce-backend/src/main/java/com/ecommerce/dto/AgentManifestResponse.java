package com.ecommerce.dto;

public class AgentManifestResponse {

    private String name;
    private String description;
    private String agentUrl;
    private String authToken;
    private String agentUsername;
    private String ownerEmail;
    private String contactPhone;

    public AgentManifestResponse() {
    }

    public AgentManifestResponse(String name, String description, String agentUrl, String authToken,
                                 String agentUsername, String ownerEmail, String contactPhone) {
        this.name = name;
        this.description = description;
        this.agentUrl = agentUrl;
        this.authToken = authToken;
        this.agentUsername = agentUsername;
        this.ownerEmail = ownerEmail;
        this.contactPhone = contactPhone;
    }

    public String getName() { return name; }
    public void setName(String name) { this.name = name; }

    public String getDescription() { return description; }
    public void setDescription(String description) { this.description = description; }

    public String getAgentUrl() { return agentUrl; }
    public void setAgentUrl(String agentUrl) { this.agentUrl = agentUrl; }

    public String getAuthToken() { return authToken; }
    public void setAuthToken(String authToken) { this.authToken = authToken; }

    public String getAgentUsername() { return agentUsername; }
    public void setAgentUsername(String agentUsername) { this.agentUsername = agentUsername; }

    public String getOwnerEmail() { return ownerEmail; }
    public void setOwnerEmail(String ownerEmail) { this.ownerEmail = ownerEmail; }

    public String getContactPhone() { return contactPhone; }
    public void setContactPhone(String contactPhone) { this.contactPhone = contactPhone; }
}
