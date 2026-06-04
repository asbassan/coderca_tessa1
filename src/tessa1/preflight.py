"""
Preflight checks for CodeRCA

Validates environment and dependencies before running investigations.
"""

import subprocess
import sys
from pathlib import Path
from typing import List, Tuple, Optional
import sqlite3
from .tooling import resolve_gh_command


class PreflightCheck:
    """Individual preflight check"""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.passed = False
        self.message = ""
    
    def __str__(self) -> str:
        status = "[OK]" if self.passed else "[FAIL]"
        return f"{status} {self.name}: {self.message}"


class PreflightValidator:
    """
    Validates CodeRCA environment and dependencies.
    
    Checks:
    - Python version
    - Required packages
    - GitHub CLI
    - eShopOnWeb setup
    - Log database
    - Context documents
    """
    
    def __init__(self):
        self.checks: List[PreflightCheck] = []
    
    def run_all_checks(self) -> bool:
        """
        Run all preflight checks.
        
        Returns:
            True if all checks passed, False otherwise
        """
        self.checks = []
        
        # Environment checks
        self.check_python_version()
        self.check_required_packages()
        
        # External tools
        self.check_dotnet_sdk()
        self.check_gh_cli()
        self.check_gh_auth()
        
        # CodeRCA setup
        self.check_context_documents()
        
        # eShopOnWeb integration
        self.check_eshop_setup()
        self.check_log_database()
        
        # Summary
        passed = sum(1 for c in self.checks if c.passed)
        total = len(self.checks)
        
        return passed == total
    
    def check_python_version(self) -> PreflightCheck:
        """Check Python version >= 3.10"""
        check = PreflightCheck("Python Version", "Requires Python 3.10+")
        
        version = sys.version_info
        check.passed = version >= (3, 10)
        check.message = f"Python {version.major}.{version.minor}.{version.micro}"
        
        if not check.passed:
            check.message += " (requires 3.10+)"
        
        self.checks.append(check)
        return check
    
    def check_required_packages(self) -> PreflightCheck:
        """Check required Python packages are installed"""
        check = PreflightCheck("Python Packages", "Required packages installed")
        
        required = ["click", "yaml"]  # Add more as needed
        missing = []
        
        for package in required:
            try:
                __import__(package)
            except ImportError:
                missing.append(package)
        
        if missing:
            check.passed = False
            check.message = f"Missing: {', '.join(missing)}"
        else:
            check.passed = True
            check.message = f"All required packages installed ({len(required)})"
        
        self.checks.append(check)
        return check
    
    def check_gh_cli(self) -> PreflightCheck:
        """Check GitHub CLI is installed"""
        check = PreflightCheck("GitHub CLI", "gh command available")
        
        try:
            result = subprocess.run(
                [resolve_gh_command(), "--version"],
                capture_output=True,
                text=True,
                check=True
            )
            version_line = result.stdout.split("\n")[0]
            check.passed = True
            check.message = version_line
        except (subprocess.CalledProcessError, FileNotFoundError):
            check.passed = False
            check.message = "gh CLI not found - install from https://cli.github.com/"
        
        self.checks.append(check)
        return check

    def check_dotnet_sdk(self) -> PreflightCheck:
        """Check .NET 8 SDK is installed"""
        check = PreflightCheck(".NET SDK", "Requires .NET 8 SDK")

        try:
            result = subprocess.run(
                ["dotnet", "--list-sdks"],
                capture_output=True,
                text=True,
                check=True
            )
            sdks = [line.strip() for line in result.stdout.splitlines() if line.strip()]
            dotnet8 = next((sdk for sdk in sdks if sdk.startswith("8.")), None)

            if dotnet8:
                check.passed = True
                check.message = f".NET SDK {dotnet8}"
            else:
                check.passed = False
                check.message = ".NET 8 SDK not found"
        except (subprocess.CalledProcessError, FileNotFoundError):
            check.passed = False
            check.message = "dotnet not found - install .NET 8 SDK"

        self.checks.append(check)
        return check
    
    def check_gh_auth(self) -> PreflightCheck:
        """Check GitHub CLI authentication"""
        check = PreflightCheck("GitHub Auth", "Authenticated with GitHub")
        
        try:
            result = subprocess.run(
                [resolve_gh_command(), "auth", "status"],
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode == 0:
                check.passed = True
                # Extract account name from output
                for line in result.stdout.split("\n"):
                    if "Logged in to github.com" in line and "account" in line:
                        # Extract account name
                        parts = line.split()
                        if len(parts) >= 6:
                            account = parts[5]
                            check.message = f"Authenticated as {account}"
                            break
                else:
                    check.message = "Authenticated"
            else:
                check.passed = False
                check.message = "Not authenticated - run 'gh auth login'"
        except Exception as e:
            check.passed = False
            check.message = f"Failed to check auth: {e}"
        
        self.checks.append(check)
        return check
    
    def check_context_documents(self) -> PreflightCheck:
        """Check context documents exist"""
        check = PreflightCheck("Context Documents", "Domain knowledge for agents")
        
        # Find context directory
        base_dir = Path(__file__).parent
        context_dir = base_dir / "context"
        
        if not context_dir.exists():
            check.passed = False
            check.message = f"Context directory not found: {context_dir}"
            self.checks.append(check)
            return check
        
        # Check for required documents
        required_docs = [
            "components/database.md",
            "components/catalog.md",
            "components/order.md",
            "components/basket.md",
            "architecture/overview.md"
        ]
        
        missing = []
        for doc in required_docs:
            if not (context_dir / doc).exists():
                missing.append(doc)
        
        if missing:
            check.passed = False
            check.message = f"Missing {len(missing)} document(s): {missing[0]}"
        else:
            total_size = sum(
                (context_dir / doc).stat().st_size 
                for doc in required_docs
            )
            check.passed = True
            check.message = f"{len(required_docs)} documents, {total_size/1024:.1f} KB"
        
        self.checks.append(check)
        return check
    
    def check_eshop_setup(self) -> PreflightCheck:
        """Check eShopOnWeb is set up"""
        check = PreflightCheck("eShopOnWeb", "Target application present")
        
        eshop_dir = Path("eshop")
        
        if not eshop_dir.exists():
            check.passed = False
            check.message = "eshop/ directory not found - run 'git submodule update --init'"
            self.checks.append(check)
            return check
        
        # Check for key files
        web_project = eshop_dir / "src" / "Web" / "Web.csproj"
        
        if not web_project.exists():
            check.passed = False
            check.message = "eShopOnWeb not properly initialized"
        else:
            check.passed = True
            check.message = "eShopOnWeb present"
        
        self.checks.append(check)
        return check
    
    def check_log_database(self) -> PreflightCheck:
        """Check log database exists and has data"""
        check = PreflightCheck("Log Database", "SQLite logs from eShopOnWeb")
        
        # Try to find log database
        candidates = [
            Path("eshop/src/Web/bin/Debug/net8.0/eshop-logs.db"),
            Path("eshop-logs.db"),
            Path("logs/eshop-logs.db")
        ]
        
        db_path = None
        for path in candidates:
            if path.exists():
                db_path = path
                break
        
        if not db_path:
            check.passed = False
            check.message = "Log database not found - run eShopOnWeb first"
            self.checks.append(check)
            return check
        
        # Check database has logs
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            count = cursor.execute("SELECT COUNT(*) FROM Logs").fetchone()[0]
            conn.close()
            
            if count == 0:
                check.passed = False
                check.message = f"Database exists but has no logs ({db_path.name})"
            else:
                check.passed = True
                check.message = f"{count} log entries in {db_path.name}"
        except Exception as e:
            check.passed = False
            check.message = f"Failed to read database: {e}"
        
        self.checks.append(check)
        return check
    
    def get_summary(self) -> str:
        """Get formatted summary of all checks"""
        lines = []
        lines.append("=" * 70)
        lines.append("CodeRCA Preflight Checks")
        lines.append("=" * 70)
        lines.append("")
        
        for check in self.checks:
            lines.append(str(check))
        
        lines.append("")
        lines.append("=" * 70)
        
        passed = sum(1 for c in self.checks if c.passed)
        total = len(self.checks)
        
        if passed == total:
            lines.append(f"[OK] All {total} checks passed")
            lines.append("CodeRCA is ready to use!")
        else:
            failed = total - passed
            lines.append(f"[FAIL] {failed}/{total} checks failed")
            lines.append("")
            lines.append("Fix the issues above before running investigations.")
        
        lines.append("=" * 70)
        
        return "\n".join(lines)
    
    def get_failed_checks(self) -> List[PreflightCheck]:
        """Get list of failed checks"""
        return [c for c in self.checks if not c.passed]


def run_preflight_checks(verbose: bool = True) -> bool:
    """
    Run all preflight checks and print results.
    
    Args:
        verbose: Print detailed results
        
    Returns:
        True if all checks passed
    """
    validator = PreflightValidator()
    all_passed = validator.run_all_checks()
    
    if verbose:
        print(validator.get_summary())
    
    return all_passed
