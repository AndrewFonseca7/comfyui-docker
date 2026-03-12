#!/bin/bash
set -e

NAME="${1:-unnamed}"
KEYS_FILE="${2:-./config/api-keys.json}"

# Generate a random 32-byte hex key
KEY=$(openssl rand -hex 32)

echo "Generated API key for '$NAME':"
echo "  $KEY"
echo ""

# Create keys file if it doesn't exist
if [ ! -f "$KEYS_FILE" ]; then
  mkdir -p "$(dirname "$KEYS_FILE")"
  echo '{"keys": []}' > "$KEYS_FILE"
fi

# Add key to the file (requires jq)
if command -v jq &>/dev/null; then
  tmp=$(mktemp)
  jq --arg key "$KEY" --arg name "$NAME" \
    '.keys += [{"key": $key, "name": $name}]' \
    "$KEYS_FILE" > "$tmp" && mv "$tmp" "$KEYS_FILE"
  echo "Key added to $KEYS_FILE"
else
  echo "Install jq to auto-add keys, or manually add to $KEYS_FILE:"
  echo "  {\"key\": \"$KEY\", \"name\": \"$NAME\"}"
fi
