import argparse
import json
import sys

from app.database import init_db, SessionLocal
from app.scripts.generator import generate_scripts
from app.youtube.upload import upload_video
from app.youtube.analytics import fetch_all_analytics
from app.trends.suggester import suggest_content
from app.feedback.scorer import update_all_scores, get_performance_insights


def cmd_generate(args):
    """Generate 5 multi-angle scripts from a content brief."""
    init_db()
    db = SessionLocal()
    try:
        print(f"\n  Generating 5 scripts for: \"{args.brief}\"\n")
        result = generate_scripts(db, args.brief)
        print(f"  Brief ID: {result['brief_id']}\n")
        print("=" * 80)

        for i, script in enumerate(result["scripts"], 1):
            print(f"\n  [{i}] {script['angle'].upper()} | Hook: {script['hook_type']}")
            print(f"  Title: {script['title']}")
            print(f"  ---")
            print(f"  Hook: {script['hook']}")
            print(f"\n  {script['body']}")
            print(f"\n  CTA ({script['cta_goal']}): {script['cta']}")
            print(f"  Thumbnail: {script.get('thumbnail_suggestion', 'N/A')}")
            print(f"  Predicted: {script.get('predicted_performance', 'N/A')}")
            print("=" * 80)

        print(f"\n  Done! {len(result['scripts'])} scripts saved.\n")
    finally:
        db.close()


def cmd_upload(args):
    """Upload a video to YouTube using a script's metadata."""
    init_db()
    db = SessionLocal()
    try:
        print(f"\n  Uploading video for script {args.script_id}...")
        result = upload_video(db, args.script_id, args.video_path, args.privacy)
        print(f"  Uploaded! YouTube Video ID: {result['youtube_video_id']}\n")
    except FileNotFoundError as e:
        print(f"\n  Auth required: {e}")
        print("  Run the API server and visit /youtube/auth to authenticate.\n")
    finally:
        db.close()


def cmd_trends(args):
    """Fetch trending topics and suggest content ideas."""
    init_db()
    db = SessionLocal()
    try:
        print("\n  Pulling trends and generating suggestions...\n")
        suggestions = suggest_content(db)

        print(f"  {'Keyword':<25} {'Source':<15} {'Score':<8} Brief")
        print(f"  {'-'*25} {'-'*15} {'-'*8} {'-'*40}")
        for s in suggestions:
            print(f"  {s['keyword']:<25} {s['source']:<15} {s['trend_score']:<8} {s['suggested_brief'][:50]}")

        print(f"\n  {len(suggestions)} suggestions saved.\n")
    finally:
        db.close()


def cmd_analytics(args):
    """Fetch latest YouTube analytics and update scores."""
    init_db()
    db = SessionLocal()
    try:
        print("\n  Fetching analytics...")
        results = fetch_all_analytics(db)
        updated = update_all_scores(db)

        print(f"  Fetched analytics for {len(results)} videos.")

        if updated:
            print(f"\n  {'Title':<40} {'Angle':<15} Score")
            print(f"  {'-'*40} {'-'*15} {'-'*8}")
            for u in updated:
                print(f"  {u['title'][:38]:<40} {u['angle']:<15} {u['score']}")

        print()
    except FileNotFoundError:
        print("\n  YouTube not authenticated. Run the API server and visit /youtube/auth first.\n")
    finally:
        db.close()


def cmd_insights(args):
    """Show performance insights."""
    init_db()
    db = SessionLocal()
    try:
        data = get_performance_insights(db)

        if "message" in data:
            print(f"\n  {data['message']}\n")
            return

        print(f"\n  Total scored scripts: {data['total_scored']}")
        print(f"  Best angle: {data['best_angle']}")
        print(f"  Best hook type: {data['best_hook']}\n")

        for category, label in [("by_angle", "Angles"), ("by_hook_type", "Hook Types"), ("by_cta_goal", "CTA Goals")]:
            print(f"  {label}:")
            for k, v in data[category].items():
                print(f"    {k:<20} avg: {v['avg_score']:<8} count: {v['count']}")
            print()
    finally:
        db.close()


def cmd_seed(args):
    """Load mock data into the database."""
    init_db()
    db = SessionLocal()
    try:
        from app.seed import seed
        if args.force:
            # Drop and recreate all tables for a clean reseed
            from app.database import engine, Base
            Base.metadata.drop_all(bind=engine)
            Base.metadata.create_all(bind=engine)
            print("\n  Database reset.")
        result = seed(db)
        if result["status"] == "seeded":
            print(f"\n  Mock data loaded:")
            for k, v in result["counts"].items():
                print(f"    {k}: {v}")
            print()
        else:
            print(f"\n  {result['message']}")
            print("  Use --force to reset and reseed.\n")
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(
        description="AI-powered social media content engine",
        prog="content-engine",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # seed
    sd = subparsers.add_parser("seed", help="Load mock data into the database")
    sd.add_argument("--force", action="store_true", help="Reset DB and reseed from scratch")
    sd.set_defaults(func=cmd_seed)

    # generate
    gen = subparsers.add_parser("generate", help="Generate 5 multi-angle scripts from a brief")
    gen.add_argument("brief", help='Content brief, e.g. "Why FD matters in 2026"')
    gen.set_defaults(func=cmd_generate)

    # upload
    up = subparsers.add_parser("upload", help="Upload a video to YouTube")
    up.add_argument("script_id", help="Script ID for video metadata")
    up.add_argument("video_path", help="Path to video file")
    up.add_argument("--privacy", default="private", choices=["private", "unlisted", "public"])
    up.set_defaults(func=cmd_upload)

    # trends
    tr = subparsers.add_parser("trends", help="Fetch trending topics and suggest content ideas")
    tr.set_defaults(func=cmd_trends)

    # analytics
    an = subparsers.add_parser("analytics", help="Fetch YouTube analytics and update scores")
    an.set_defaults(func=cmd_analytics)

    # insights
    ins = subparsers.add_parser("insights", help="Show performance insights")
    ins.set_defaults(func=cmd_insights)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
