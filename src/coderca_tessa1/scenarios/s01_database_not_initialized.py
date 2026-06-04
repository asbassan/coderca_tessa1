"""
S01: Database Not Initialized

Scenario: eShopOnWeb app starts but database migrations have not been run.
Expected: SqliteException "no such table" errors for CatalogBrands, etc.
Expected Agents: DatabaseAgent, CatalogAgent
Expected Root Cause: "Database tables do not exist - migrations not applied"
"""

import os
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from .base import Scenario, ScenarioSeverity


class S01DatabaseNotInitialized(Scenario):
    """
    S01: Database Not Initialized
    
    Simulates starting the eShopOnWeb application when database
    migrations have not been applied.
    """
    
    @property
    def name(self) -> str:
        return "Database Not Initialized"
    
    @property
    def description(self) -> str:
        return (
            "eShopOnWeb application starts but database migrations have not been run. "
            "Expected outcome: SqliteException 'no such table' errors for catalog tables. "
            "DatabaseAgent and CatalogAgent should be selected to investigate."
        )
    
    @property
    def severity(self) -> ScenarioSeverity:
        return ScenarioSeverity.CRITICAL
    
    def inject_fault(self) -> Dict[str, Any]:
        """
        Inject fault by removing/renaming database files.
        
        This forces the app to create empty database files without tables.
        """
        print(f"\n[S01] Injecting fault: Database Not Initialized")
        
        # Find database files
        db_paths = [
            Path("eshop/src/Web/bin/Debug/net8.0/catalog.db"),
            Path("eshop/src/Web/bin/Debug/net8.0/identity.db")
        ]
        
        backed_up = []
        for db_path in db_paths:
            if db_path.exists():
                backup_path = db_path.with_suffix(f".db.backup.{int(time.time())}")
                shutil.move(str(db_path), str(backup_path))
                backed_up.append(str(backup_path))
                print(f"  [OK] Backed up {db_path.name} to {backup_path.name}")
        
        print(f"  [OK] Fault injected - databases removed")
        print(f"  [INFO] On next app start, empty databases will be created")
        print(f"  [INFO] Expected: 'no such table' errors")
        
        return {
            "fault_type": "database_not_initialized",
            "databases_backed_up": backed_up,
            "injection_time": datetime.now().isoformat()
        }
    
    def cleanup(self):
        """
        Restore backed up database files.
        """
        print(f"\n[S01] Cleaning up fault...")
        
        # Find backup files
        backup_pattern = "*.db.backup.*"
        eshop_dir = Path("eshop/src/Web/bin/Debug/net8.0")
        
        if not eshop_dir.exists():
            print(f"  [SKIP] eShopOnWeb directory not found")
            return
        
        backups = list(eshop_dir.glob(backup_pattern))
        
        if not backups:
            print(f"  [INFO] No backup files found")
            return
        
        for backup_path in backups:
            # Restore original name
            original_name = backup_path.name.split('.backup.')[0] + ".db"
            original_path = backup_path.parent / original_name
            
            if original_path.exists():
                original_path.unlink()
            
            shutil.move(str(backup_path), str(original_path))
            print(f"  [OK] Restored {original_name}")
        
        print(f"  [OK] Cleanup complete")
    
    def verify_telemetry(self, logs_generated: int, errors_generated: int) -> bool:
        """
        Verify expected telemetry.
        
        Expected: Multiple SqliteException errors with "no such table" message.
        """
        # For this scenario, we expect errors
        if errors_generated == 0:
            print(f"  [WARN] No errors generated - expected SqliteException errors")
            return False
        
        print(f"  [OK] Telemetry verified: {errors_generated} errors (expected > 0)")
        return True
    
    def get_expected_agents(self) -> list:
        """Expected: DatabaseAgent and CatalogAgent"""
        return ["DatabaseAgent", "CatalogAgent"]
    
    def get_expected_root_cause(self) -> str:
        """Expected root cause"""
        return "Database tables do not exist - migrations not applied"
