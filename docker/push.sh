#!/bin/bash

TAG_WITH_HEX=false

# Parse command line arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --tag) TAG_WITH_HEX=true ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

# Generate random hex if tagging is enabled
if [ "$TAG_WITH_HEX" = true ]; then
    RANDOM_HEX=$(openssl rand -hex 2)
    echo "Generated random hex suffix: $RANDOM_HEX"
fi

# Define image variants
VARIANTS=("minimal" "basic" "example" "eval")

# Tag and push each variant
for variant in "${VARIANTS[@]}"; do
    echo "Processing variant: $variant"

    # Push the main tag
    echo "Pushing: ghcr.io/gradion-ai/ipybox:$variant"
    docker push "ghcr.io/gradion-ai/ipybox:$variant"

    # Only tag and push with hex if --tag option was provided
    if [ "$TAG_WITH_HEX" = true ]; then
        echo "Tagging: ghcr.io/gradion-ai/ipybox:$variant-$RANDOM_HEX"
        docker tag "ghcr.io/gradion-ai/ipybox:$variant" "ghcr.io/gradion-ai/ipybox:$variant-$RANDOM_HEX"

        echo "Pushing: ghcr.io/gradion-ai/ipybox:$variant-$RANDOM_HEX"
        docker push "ghcr.io/gradion-ai/ipybox:$variant-$RANDOM_HEX"
    fi

    echo "Completed processing $variant"
    echo "-------------------"
done

echo "All variants processed successfully"
