#!/usr/bin/env python3
"""
Hypermage Scene Invocation CLI
================================
Sends a natural language scene description to the ProducerOrchestrator agent,
which delegates to EnvironmentDesigner to produce a validated ScenePlan.json
saved to S3.

Usage:
    python scripts/invoke.py "a neon-lit cyberspace node for a cyberpunk LARP"
    python scripts/invoke.py "a sacred forest ritual circle at dusk" --platforms vr web
    python scripts/invoke.py "an abandoned space station, horror atmosphere" --type exploration

Options:
    --type      Scene type hint: exploration|ritual|cyberspace|social|combat|sanctuary|hybrid
    --platforms Space-separated list: vr web (default: vr web)
    --save      Also save the raw response to a local JSON file
    --region    AWS region (default: eu-west-1)
"""

import argparse
import json
import sys
import boto3
from botocore.config import Config

ENVIRONMENT_DESIGNER_ARN = (
    "arn:aws:bedrock-agentcore:eu-west-1:732231126129:"
    "runtime/ConversationLevelDesigner_Agent-1ZShl1E6H5"
)
AWS_REGION = "eu-west-1"


def invoke_orchestrator(prompt: str, region: str = AWS_REGION) -> str:
    """Invoke the EnvironmentDesigner AgentCore runtime and return the full response text."""
    client = boto3.client(
        "bedrock-agentcore",
        region_name=region,
        config=Config(read_timeout=300, connect_timeout=10),
    )
    resp = client.invoke_agent_runtime(
        agentRuntimeArn=ENVIRONMENT_DESIGNER_ARN,
        payload=json.dumps({"prompt": prompt}).encode("utf-8"),
    )

    raw = resp["response"].read().decode("utf-8")

    # Parse SSE: data: "chunk"
    chunks = []
    for line in raw.split("\n"):
        if line.startswith("data: "):
            value = line[6:].strip()
            if value.startswith('"') and value.endswith('"'):
                try:
                    value = json.loads(value)
                except json.JSONDecodeError:
                    pass
            chunks.append(value)

    return "".join(chunks)


def extract_scene_plan(response_text: str) -> dict | None:
    """Try to extract a ScenePlan JSON object from the agent response."""
    # Agent may wrap JSON in markdown code blocks
    text = response_text
    if "```json" in text:
        start = text.find("```json") + 7
        end = text.find("```", start)
        text = text[start:end].strip()
    elif "```" in text:
        start = text.find("```") + 3
        end = text.find("```", start)
        text = text[start:end].strip()

    # Try to find outermost JSON object
    brace_start = text.find("{")
    if brace_start == -1:
        return None

    depth = 0
    for i, ch in enumerate(text[brace_start:], brace_start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[brace_start:i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def main():
    parser = argparse.ArgumentParser(description="Invoke Hypermage scene generation")
    parser.add_argument("description", help="Natural language scene description")
    parser.add_argument(
        "--type",
        choices=["exploration", "ritual", "cyberspace", "social", "combat", "sanctuary", "hybrid"],
        help="Scene type hint (optional — agent will infer if not set)",
    )
    parser.add_argument(
        "--platforms",
        nargs="+",
        choices=["vr", "web"],
        default=["vr", "web"],
        help="Target platforms (default: vr web)",
    )
    parser.add_argument("--save", metavar="FILE", help="Save full response to a JSON file")
    parser.add_argument("--region", default=AWS_REGION, help="AWS region")
    args = parser.parse_args()

    # Build enriched prompt
    prompt_parts = [f"Design a scene for: {args.description}"]
    if args.type:
        prompt_parts.append(f"Scene type: {args.type}")
    prompt_parts.append(f"Target platforms: {', '.join(args.platforms)}")
    prompt_parts.append(
        "Generate a complete ScenePlan, validate it, and save it to S3. "
        "Return the ScenePlan JSON and S3 URI."
    )
    prompt = "\n".join(prompt_parts)

    print("\nHypermage Scene Generator")
    print("-" * 50)
    print(f"Description : {args.description}")
    if args.type:
        print(f"Type        : {args.type}")
    print(f"Platforms   : {', '.join(args.platforms)}")
    print("\nInvoking EnvironmentDesigner...")

    try:
        response = invoke_orchestrator(prompt, region=args.region)
    except Exception as e:
        print(f"\nERROR: Invocation failed: {e}", file=sys.stderr)
        sys.exit(1)

    print("\n" + "-" * 50)
    print("Agent response:\n")
    print(response)
    print("\n" + "-" * 50)

    # Try to surface the ScenePlan cleanly
    scene_plan = extract_scene_plan(response)
    if scene_plan:
        scene_name = scene_plan.get("name", "unknown")
        scene_id = scene_plan.get("id", "unknown")
        zones = len(scene_plan.get("zones", []))
        hooks = len(scene_plan.get("gm_hooks", []))
        states = len(scene_plan.get("narrative_states", []))
        print("\nScenePlan extracted:")
        print(f"  Name       : {scene_name}")
        print(f"  ID         : {scene_id}")
        print(f"  Zones      : {zones}")
        print(f"  GM hooks   : {hooks}")
        print(f"  Narrative  : {states} states")
        print(f"  Platforms  : {', '.join(scene_plan.get('platforms', []))}")
        print(f"\n  S3 URI     : s3://hypermage-vr-unreal-build-artifacts-dev/scene-plans/{scene_id}/scene_plan.json")
    else:
        print("\n(Could not extract ScenePlan JSON from response -- see full response above)")

    if args.save:
        output = {"prompt": args.description, "response": response, "scene_plan": scene_plan}
        with open(args.save, "w") as f:
            json.dump(output, f, indent=2)
        print(f"\nFull response saved to: {args.save}")


if __name__ == "__main__":
    main()
