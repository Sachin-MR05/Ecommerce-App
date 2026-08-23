package com.ecommerce.auth;

import com.ecommerce.exception.AuthException;
import com.ecommerce.model.Role;
import com.ecommerce.model.User;
import com.ecommerce.repository.UserRepository;
import com.ecommerce.security.JwtService;
import com.ecommerce.security.UserPrincipal;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.BadCredentialsException;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

@Service
public class AuthService {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final AuthenticationManager authenticationManager;
    private final JwtService jwtService;

    @Value("${app.security.admin-invite-code}")
    private String adminInviteCode;

    public AuthService(UserRepository userRepository, PasswordEncoder passwordEncoder,
                        AuthenticationManager authenticationManager, JwtService jwtService) {
        this.userRepository = userRepository;
        this.passwordEncoder = passwordEncoder;
        this.authenticationManager = authenticationManager;
        this.jwtService = jwtService;
    }

    public AuthResponse register(RegisterRequest request) {
        if (userRepository.existsByEmail(request.getEmail())) {
            throw new AuthException("An account with this email already exists");
        }
        if (userRepository.existsByUsername(request.getUsername())) {
            throw new AuthException("This username is already taken");
        }

        Role role = resolveRole(request);

        User user = new User(
                request.getUsername(),
                request.getEmail(),
                passwordEncoder.encode(request.getPassword()),
                role
        );
        User saved = userRepository.save(user);

        UserPrincipal principal = UserPrincipal.fromEntity(saved);
        String token = jwtService.generateToken(principal);

        return new AuthResponse(token, saved.getId(), saved.getUsername(), saved.getEmail(), saved.getRole().name());
    }

    public AuthResponse login(LoginRequest request) {
        try {
            authenticationManager.authenticate(
                    new UsernamePasswordAuthenticationToken(request.getEmail(), request.getPassword())
            );
        } catch (BadCredentialsException e) {
            throw new AuthException("Invalid email or password");
        }

        User user = userRepository.findByEmail(request.getEmail())
                .orElseThrow(() -> new AuthException("Invalid email or password"));

        UserPrincipal principal = UserPrincipal.fromEntity(user);
        String token = jwtService.generateToken(principal);

        return new AuthResponse(token, user.getId(), user.getUsername(), user.getEmail(), user.getRole().name());
    }

    private Role resolveRole(RegisterRequest request) {
        String requested = request.getRole();
        if (requested == null || requested.isBlank() || "CUSTOMER".equalsIgnoreCase(requested)) {
            return Role.CUSTOMER;
        }
        if ("ADMIN".equalsIgnoreCase(requested)) {
            if (adminInviteCode == null || !adminInviteCode.equals(request.getAdminCode())) {
                throw new AuthException("Invalid admin invite code");
            }
            return Role.ADMIN;
        }
        throw new AuthException("Role must be either CUSTOMER or ADMIN");
    }
}
