package com.ecommerce.service;

import com.ecommerce.dto.AgentManifestResponse;
import com.ecommerce.model.Role;
import com.ecommerce.model.User;
import com.ecommerce.repository.UserRepository;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.UUID;

@Service
public class AgentUserService {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;

    public AgentUserService(UserRepository userRepository, PasswordEncoder passwordEncoder) {
        this.userRepository = userRepository;
        this.passwordEncoder = passwordEncoder;
    }

    @Transactional
    public User getOrCreateAgentForUser(Long parentUserId) {
        return userRepository.findByAgentOfUserId(parentUserId)
                .orElseGet(() -> {
                    String agentUsername = "agent_user_" + parentUserId;
                    // In case username exists, append a random suffix
                    if (userRepository.existsByUsername(agentUsername)) {
                        agentUsername += "_" + UUID.randomUUID().toString().substring(0, 6);
                    }

                    String agentEmail = "agent_" + parentUserId + "@internal.agent";
                    if (userRepository.existsByEmail(agentEmail)) {
                        agentEmail = "agent_" + parentUserId + "_" + UUID.randomUUID().toString().substring(0, 6) + "@internal.agent";
                    }

                    String dummyPassword = passwordEncoder.encode(UUID.randomUUID().toString());

                    User agentUser = new User(
                            agentUsername,
                            agentEmail,
                            dummyPassword,
                            Role.CUSTOMER,
                            parentUserId
                    );
                    return userRepository.save(agentUser);
                });
    }

    public AgentManifestResponse getManifestForUser(Long parentUserId) {
        User agentUser = getOrCreateAgentForUser(parentUserId);
        // Look up the owner's email (needed for the manifest)
        String ownerEmail = userRepository.findById(parentUserId)
                .map(User::getEmail)
                .orElse("unknown@internal.agent");
        return new AgentManifestResponse(
                "TechHaven India",
                "Electronics, smartphones, and accessories",
                "http://localhost:8001/agent/message",
                "Bearer dev-token-techhaven",
                agentUser.getUsername(),
                ownerEmail,
                "+91 90000 00001"
        );
    }

    public List<Long> getAllAgentUserIds() {
        return userRepository.findByAgentOfUserIdIsNotNull().stream()
                .map(User::getId)
                .toList();
    }
}

