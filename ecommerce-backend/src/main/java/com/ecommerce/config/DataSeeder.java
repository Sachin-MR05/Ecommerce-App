package com.ecommerce.config;

import com.ecommerce.model.Product;
import com.ecommerce.model.Role;
import com.ecommerce.model.User;
import com.ecommerce.repository.ProductRepository;
import com.ecommerce.repository.UserRepository;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.CommandLineRunner;
import org.springframework.core.io.ClassPathResource;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;

import java.util.List;

/**
 * Runs once on startup:
 *  - if the "products" table is empty, loads the old products.json seed data into Postgres
 *  - if there are no users yet, creates a default admin account so you can log in immediately
 */
@Component
public class DataSeeder implements CommandLineRunner {

    private static final Logger log = LoggerFactory.getLogger(DataSeeder.class);

    private final ProductRepository productRepository;
    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final ObjectMapper objectMapper = new ObjectMapper();

    @Value("${app.seed.products-file}")
    private String seedFile;

    @Value("${app.seed.admin-username}")
    private String adminUsername;

    @Value("${app.seed.admin-email}")
    private String adminEmail;

    @Value("${app.seed.admin-password}")
    private String adminPassword;

    public DataSeeder(ProductRepository productRepository, UserRepository userRepository,
                       PasswordEncoder passwordEncoder) {
        this.productRepository = productRepository;
        this.userRepository = userRepository;
        this.passwordEncoder = passwordEncoder;
    }

    @Override
    public void run(String... args) throws Exception {
        seedProducts();
        seedAdminUser();
    }

    private void seedProducts() {
        if (productRepository.count() > 0) {
            return;
        }

        try {
            ClassPathResource resource = new ClassPathResource(seedFile);
            if (!resource.exists()) {
                log.info("No seed file found at {}, skipping product seed", seedFile);
                return;
            }

            List<Product> seedProducts = objectMapper.readValue(
                    resource.getInputStream(),
                    objectMapper.getTypeFactory().constructCollectionType(List.class, Product.class));

            // id is DB-generated now, so clear the old JSON ids before saving
            seedProducts.forEach(p -> p.setId(null));

            productRepository.saveAll(seedProducts);
            log.info("Seeded {} products into the database", seedProducts.size());
        } catch (Exception e) {
            log.warn("Could not seed products from {}: {}", seedFile, e.getMessage());
        }
    }

    private void seedAdminUser() {
        if (userRepository.existsByEmail(adminEmail)) {
            return;
        }

        User admin = new User(adminUsername, adminEmail, passwordEncoder.encode(adminPassword), Role.ADMIN);
        userRepository.save(admin);
        log.info("Created default admin account -> email: {}  password: {}", adminEmail, adminPassword);
    }
}
