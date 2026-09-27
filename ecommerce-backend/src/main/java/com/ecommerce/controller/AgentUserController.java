package com.ecommerce.controller;

import com.ecommerce.dto.AgentManifestResponse;
import com.ecommerce.security.CurrentUser;
import com.ecommerce.security.UserPrincipal;
import com.ecommerce.service.AgentUserService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/agent")
public class AgentUserController {

    private final AgentUserService agentUserService;

    public AgentUserController(AgentUserService agentUserService) {
        this.agentUserService = agentUserService;
    }

    /**
     * Authenticated endpoint: returns the personalized manifest for the logged-in customer,
     * provisioning a dedicated agent user ID if one does not already exist.
     */
    @GetMapping("/manifest")
    public ResponseEntity<AgentManifestResponse> getManifest(@CurrentUser UserPrincipal principal) {
        if (principal == null) {
            return ResponseEntity.ok(getDefaultManifest());
        }
        return ResponseEntity.ok(agentUserService.getManifestForUser(principal.getId()));
    }

    /**
     * Public endpoint: returns the fallback manifest with default userId=1.
     */
    @GetMapping("/manifest/public")
    public ResponseEntity<AgentManifestResponse> getPublicManifest() {
        return ResponseEntity.ok(getDefaultManifest());
    }

    /**
     * Returns all agent user IDs currently registered in the system.
     */
    @GetMapping("/ids")
    public ResponseEntity<List<Long>> getAllAgentIds() {
        return ResponseEntity.ok(agentUserService.getAllAgentUserIds());
    }

    private AgentManifestResponse getDefaultManifest() {
        return new AgentManifestResponse(
                "TechHaven India",
                "Electronics, smartphones, and accessories",
                "http://localhost:8001/agent/message",
                "Bearer dev-token-techhaven",
                "agent_user_1",
                "admin@example.com",
                "+91 90000 00001"
        );
    }
}

