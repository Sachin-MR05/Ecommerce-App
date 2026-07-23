package com.ecommerce.util;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import org.springframework.stereotype.Component;

import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

/**
 * Generic helper that treats a JSON file as a "table".
 *
 * Reads the whole file into a List<T> and writes a List<T> back out.
 * This is intentionally simple (read-modify-write, no locking) since
 * it's meant for a single-user dev/learning project, not production
 * concurrent writes.
 */
@Component
public class JsonUtil {

    private final ObjectMapper objectMapper;

    public JsonUtil() {
        this.objectMapper = new ObjectMapper();
        this.objectMapper.enable(SerializationFeature.INDENT_OUTPUT);
    }

    /**
     * Reads a JSON array file into a List of the given type.
     * Returns an empty list if the file doesn't exist or is empty,
     * instead of throwing - so a fresh checkout with no data files
     * still boots cleanly.
     */
    public <T> List<T> readList(String filePath, Class<T> type) {
        try {
            File file = new File(filePath);

            if (!file.exists() || file.length() == 0) {
                return new ArrayList<>();
            }

            com.fasterxml.jackson.databind.type.CollectionType listType =
                    objectMapper.getTypeFactory().constructCollectionType(List.class, type);

            return objectMapper.readValue(file, listType);
        } catch (IOException e) {
            throw new RuntimeException("Failed to read JSON file: " + filePath, e);
        }
    }

    /**
     * Writes a List back out as a pretty-printed JSON array,
     * overwriting the existing file. Creates parent directories
     * if they don't exist yet.
     */
    public <T> void writeList(String filePath, List<T> list) {
        try {
            Path path = Path.of(filePath);
            if (path.getParent() != null) {
                Files.createDirectories(path.getParent());
            }
            objectMapper.writeValue(new File(filePath), list);
        } catch (IOException e) {
            throw new RuntimeException("Failed to write JSON file: " + filePath, e);
        }
    }
}