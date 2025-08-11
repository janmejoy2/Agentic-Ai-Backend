import os
import shutil
import atexit
import signal
import sys
import yaml
from typing import Optional, Dict, Any


def load_cleanup_config() -> Dict[str, Any]:
    """
    Load cleanup configuration from integration.yml.
    
    Returns:
        dict: Cleanup configuration with defaults
    """
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(os.path.dirname(current_dir), "integration.yml")
        
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Get cleanup config with defaults
        cleanup_config = config.get('cleanup', {})
        
        return {
            'auto_cleanup': cleanup_config.get('auto_cleanup', True),
            'cleanup_on_startup': cleanup_config.get('cleanup_on_startup', False),
            'cleanup_diagrams': cleanup_config.get('cleanup_diagrams', True)
        }
        
    except Exception as e:
        print(f"⚠️ Could not load cleanup config, using defaults: {e}")
        # Return safe defaults
        return {
            'auto_cleanup': True,
            'cleanup_on_startup': False,
            'cleanup_diagrams': True
        }


def cleanup_directories(force: bool = False) -> dict:
    """
    Clean up temporary directories and files based on configuration.
    Note: generated_service folder is always preserved.
    
    Args:
        force (bool): Ignored - kept for API compatibility
        
    Returns:
        dict: Cleanup results with status and details
    """
    config = load_cleanup_config()
    
    results = {
        'success': True,
        'cleaned_folders': [],
        'skipped_folders': [],
        'errors': [],
        'force_cleanup': force,
        'config_used': config
    }
    
    try:
        print("🧹 Regular cleanup initiated...")
        print(f"📋 Using config: auto_cleanup={config['auto_cleanup']}")
        
        # Stop Spring Boot server if running
        try:
            from agents.agent4_build_deploy import stop_spring_boot_server
            stop_spring_boot_server()
        except Exception as e:
            print(f"⚠️ Could not stop Spring Boot server: {e}")
        
        # Clean up diagrams folder (if enabled in config)
        if config['cleanup_diagrams']:
            diagrams_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'diagrams')
            if os.path.exists(diagrams_dir):
                try:
                    shutil.rmtree(diagrams_dir)
                    print(f"✅ Deleted diagrams folder: {diagrams_dir}")
                    results['cleaned_folders'].append('diagrams')
                except Exception as e:
                    error_msg = f"Could not delete diagrams folder: {e}"
                    print(f"⚠️ {error_msg}")
                    results['errors'].append(error_msg)
        else:
            print("⏭️ Skipping diagrams cleanup (disabled in config)")
            results['skipped_folders'].append('diagrams (disabled in config)')
        
        # Note: generated_service folder is always preserved
        print("💡 Preserving generated_service folder (workspace is kept for inspection)")
        results['skipped_folders'].append('generated_service (always preserved)')
        
        print("🧹 Regular cleanup completed!")
            
    except Exception as e:
        error_msg = f"Error during cleanup: {e}"
        print(f"❌ {error_msg}")
        results['errors'].append(error_msg)
        results['success'] = False
    
    return results


def cleanup_on_shutdown() -> None:
    """
    Clean up temporary directories and files before server shutdown.
    This function respects the auto_cleanup configuration.
    """
    config = load_cleanup_config()
    
    if not config['auto_cleanup']:
        print("⏭️ Auto cleanup disabled in config, skipping shutdown cleanup")
        return
    
    print("🔄 Server shutting down, cleaning up temporary files...")
    cleanup_directories(force=False)


def cleanup_with_force() -> None:
    """
    Force cleanup that deletes everything, including Git repositories.
    Use with caution! This overrides configuration settings.
    """
    cleanup_directories(force=True)


def setup_cleanup_handlers() -> None:
    """
    Set up cleanup handlers for graceful shutdown.
    This function respects the auto_cleanup configuration.
    """
    config = load_cleanup_config()
    
    if not config['auto_cleanup']:
        print("⏭️ Auto cleanup disabled in config, skipping handler setup")
        return
    
    # Register cleanup function to run on normal exit
    atexit.register(cleanup_on_shutdown)
    
    # Register signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        """Handle shutdown signals gracefully."""
        print(f"\n📡 Received signal {signum}, initiating graceful shutdown...")
        cleanup_on_shutdown()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # Termination signal
    
    print("🔧 Cleanup handlers registered successfully")
    
    # Optional: Clean up on startup if configured
    if config['cleanup_on_startup']:
        print("🧹 Cleanup on startup enabled, cleaning up now...")
        cleanup_directories(force=False)


def get_cleanup_status() -> dict:
    """
    Get the current status of directories that would be cleaned up.
    
    Returns:
        dict: Status of directories
    """
    config = load_cleanup_config()
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    diagrams_dir = os.path.join(base_dir, 'diagrams')
    generated_service_dir = os.path.join(base_dir, 'generated_service')
    
    status = {
        'config': config,
        'diagrams': {
            'exists': os.path.exists(diagrams_dir),
            'path': diagrams_dir,
            'size': _get_directory_size(diagrams_dir) if os.path.exists(diagrams_dir) else 0,
            'cleanup_enabled': config['cleanup_diagrams']
        },
        'generated_service': {
            'exists': os.path.exists(generated_service_dir),
            'path': generated_service_dir,
            'is_git_repo': os.path.exists(os.path.join(generated_service_dir, '.git')) if os.path.exists(generated_service_dir) else False,
            'size': _get_directory_size(generated_service_dir) if os.path.exists(generated_service_dir) else 0,
            'cleanup_enabled': False, # Always False as it's preserved
            'preserve_git_repos': False # Always False as it's preserved
        }
    }
    
    return status


def _get_directory_size(directory: str) -> int:
    """
    Calculate the total size of a directory in bytes.
    
    Args:
        directory (str): Path to the directory
        
    Returns:
        int: Total size in bytes
    """
    total_size = 0
    try:
        for dirpath, dirnames, filenames in os.walk(directory):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                if os.path.exists(filepath):
                    total_size += os.path.getsize(filepath)
    except Exception:
        pass
    return total_size


def format_size(size_bytes: int) -> str:
    """
    Format bytes into human-readable format.
    
    Args:
        size_bytes (int): Size in bytes
        
    Returns:
        str: Formatted size string
    """
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f} {size_names[i]}"
