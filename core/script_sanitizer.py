# Script Sanitizer - AST-based pre-execution analysis and GUI stripping
# Catches syntax errors, removes headless-incompatible code, estimates complexity
import ast
import re
import logging
from typing import List, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class SanitizeResult:
    """Result of pre-execution script sanitization."""
    success: bool                          # Whether sanitization succeeded (no syntax errors)
    cleaned_script: str                    # The sanitized script with GUI calls removed
    syntax_errors: List[str] = field(default_factory=list)     # Syntax errors found
    gui_removals: List[str] = field(default_factory=list)      # GUI references that were stripped
    warnings: List[str] = field(default_factory=list)          # Non-fatal warnings
    suggested_timeout: int = 120           # Dynamic timeout based on complexity
    complexity: str = "medium"             # "simple", "medium", "complex"
    has_document_creation: bool = False    # Whether script creates a FreeCAD document
    estimated_line_count: int = 0          # Non-blank, non-comment lines


class ScriptSanitizer:
    """
    AST-based pre-execution analysis and cleanup for FreeCAD scripts.
    
    Runs BEFORE FreeCADCmd.exe to:
    - Catch SyntaxError/IndentationError instantly
    - Strip GUI-only references (ViewObject, FreeCADGui, ShapeColor, etc.)
    - Estimate script complexity for dynamic timeout allocation
    - Validate that the script creates a FreeCAD document
    """
    
    # Attributes that only exist in GUI mode and crash in headless FreeCADCmd
    GUI_ATTRIBUTES = {
        'ViewObject', 'ShapeColor', 'LineColor', 'PointColor',
        'Transparency', 'DisplayMode', 'LineWidth', 'PointSize',
        'Selectable', 'Visibility', 'DiffuseColor', 'DrawStyle',
        'Lighting', 'BoundingBox',
    }
    
    # Modules/names that don't exist in headless mode
    GUI_MODULES = {
        'FreeCADGui', 'Gui',
    }
    
    # Method calls that are GUI-only
    GUI_METHODS = {
        'Part.show', 'Draft.autogroup', 'Gui.ActiveDocument',
        'Gui.activeDocument', 'Gui.ActiveView', 'Gui.activeView',
        'Gui.SendMsgToActiveView', 'Gui.runCommand',
        'Gui.Selection', 'FreeCADGui.getMainWindow',
        'FreeCADGui.addModule',
    }
    
    def sanitize(self, script: str) -> SanitizeResult:
        """
        Analyze and clean a FreeCAD script for headless execution.
        
        Returns a SanitizeResult with the cleaned script and diagnostics.
        """
        result = SanitizeResult(
            success=True,
            cleaned_script=script,
            estimated_line_count=self._count_effective_lines(script),
        )
        
        # Step 1: Check for syntax errors via AST parsing
        try:
            ast.parse(script)
        except SyntaxError as e:
            result.success = False
            line_info = f" (line {e.lineno})" if e.lineno else ""
            result.syntax_errors.append(
                f"SyntaxError{line_info}: {e.msg}"
            )
            # Can't do AST-based cleaning on unparseable code, fall back to regex
            result.cleaned_script = self._regex_strip_gui(script, result)
            result.suggested_timeout = self._estimate_timeout_from_lines(result.estimated_line_count)
            result.complexity = self._classify_complexity_from_lines(result.estimated_line_count)
            return result
        
        # Step 2: AST-based GUI stripping
        result.cleaned_script = self._ast_strip_gui(script, result)
        
        # Step 3: Check for document creation
        result.has_document_creation = self._check_document_creation(script)
        if not result.has_document_creation:
            result.warnings.append(
                "No document creation found (e.g., App.newDocument()). "
                "The script may not produce any output."
            )
        
        # Step 4: Estimate complexity and set dynamic timeout
        complexity_info = self._estimate_complexity(script)
        result.complexity = complexity_info["level"]
        result.suggested_timeout = complexity_info["timeout"]
        
        if complexity_info.get("warnings"):
            result.warnings.extend(complexity_info["warnings"])
        
        return result
    
    def _count_effective_lines(self, script: str) -> int:
        """Count non-blank, non-comment lines."""
        count = 0
        for line in script.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith('#'):
                count += 1
        return count
    
    def _ast_strip_gui(self, script: str, result: SanitizeResult) -> str:
        """
        Use AST to identify and comment out GUI-only lines.
        
        Rather than modifying the AST (which loses formatting/comments),
        we identify problematic line numbers via AST, then comment them out
        in the source text. This preserves the script structure.
        """
        try:
            tree = ast.parse(script)
        except SyntaxError:
            return self._regex_strip_gui(script, result)
        
        lines_to_comment = set()
        
        for node in ast.walk(tree):
            # Check for GUI module imports: import FreeCADGui / from Gui import ...
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if self._is_gui_import(node):
                    lines_to_comment.add(node.lineno)
                    result.gui_removals.append(
                        f"Line {node.lineno}: GUI import removed"
                    )
            
            # Check for attribute access: obj.ViewObject, obj.ShapeColor, etc.
            elif isinstance(node, ast.Attribute):
                if node.attr in self.GUI_ATTRIBUTES:
                    # Find the statement containing this attribute
                    stmt_line = self._find_statement_line(tree, node.lineno)
                    if stmt_line:
                        lines_to_comment.add(stmt_line)
                        result.gui_removals.append(
                            f"Line {stmt_line}: .{node.attr} access removed (headless incompatible)"
                        )
            
            # Check for GUI module references: Gui.ActiveView, FreeCADGui.xxx
            elif isinstance(node, ast.Name):
                if node.id in self.GUI_MODULES:
                    stmt_line = self._find_statement_line(tree, node.lineno)
                    if stmt_line:
                        lines_to_comment.add(stmt_line)
                        result.gui_removals.append(
                            f"Line {stmt_line}: {node.id} reference removed"
                        )
            
            # Check for calls like Part.show(...)
            elif isinstance(node, ast.Call):
                call_str = self._get_call_string(node)
                if call_str and any(call_str.startswith(gm) for gm in self.GUI_METHODS):
                    stmt_line = self._find_statement_line(tree, node.lineno)
                    if stmt_line:
                        lines_to_comment.add(stmt_line)
                        result.gui_removals.append(
                            f"Line {stmt_line}: {call_str}() call removed"
                        )
        
        # Comment out the identified lines
        if lines_to_comment:
            script_lines = script.splitlines()
            for line_no in sorted(lines_to_comment):
                idx = line_no - 1  # AST uses 1-based line numbers
                if 0 <= idx < len(script_lines):
                    original = script_lines[idx]
                    indent = len(original) - len(original.lstrip())
                    script_lines[idx] = (' ' * indent + 
                        '# [SANITIZER REMOVED - headless incompatible] ' + 
                        original.lstrip())
            
            return '\n'.join(script_lines)
        
        return script
    
    def _regex_strip_gui(self, script: str, result: SanitizeResult) -> str:
        """
        Fallback regex-based GUI stripping for scripts that can't be AST-parsed.
        Less precise but handles syntax-error scripts.
        """
        lines = script.splitlines()
        patterns = [
            (r'^\s*(import\s+FreeCADGui)', 'GUI import'),
            (r'^\s*(from\s+FreeCADGui\s+import)', 'GUI import'),
            (r'^\s*(import\s+Gui)', 'GUI import'),
            (r'^\s*.*\.ViewObject', 'ViewObject access'),
            (r'^\s*.*\.ShapeColor', 'ShapeColor access'),
            (r'^\s*.*\.LineColor', 'LineColor access'),
            (r'^\s*.*\.Transparency', 'Transparency access'),
            (r'^\s*.*\.DisplayMode', 'DisplayMode access'),
            (r'^\s*Gui\.', 'GUI module call'),
            (r'^\s*FreeCADGui\.', 'FreeCADGui call'),
            (r'^\s*Part\.show\s*\(', 'Part.show call'),
        ]
        
        for i, line in enumerate(lines):
            for pattern, desc in patterns:
                if re.match(pattern, line):
                    indent = len(line) - len(line.lstrip())
                    lines[i] = (' ' * indent + 
                        '# [SANITIZER REMOVED - ' + desc + '] ' + 
                        line.lstrip())
                    result.gui_removals.append(
                        f"Line {i + 1}: {desc} removed (regex fallback)"
                    )
                    break
        
        return '\n'.join(lines)
    
    def _is_gui_import(self, node) -> bool:
        """Check if an import statement imports GUI-only modules."""
        if isinstance(node, ast.Import):
            return any(alias.name in self.GUI_MODULES or 
                      alias.name == 'FreeCADGui' 
                      for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            return (node.module in self.GUI_MODULES or 
                    node.module == 'FreeCADGui')
        return False
    
    def _find_statement_line(self, tree: ast.AST, target_line: int) -> Optional[int]:
        """
        Find the starting line of the statement containing target_line.
        This handles cases where an attribute access is inside a larger expression.
        """
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.stmt) and hasattr(node, 'lineno'):
                # Check if target_line falls within this statement
                end_line = getattr(node, 'end_lineno', node.lineno)
                if node.lineno <= target_line <= end_line:
                    return node.lineno
        return target_line  # fallback to the line itself
    
    def _get_call_string(self, node: ast.Call) -> Optional[str]:
        """Extract the callable name string from a Call node (e.g., 'Part.show')."""
        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                return f"{node.func.value.id}.{node.func.attr}"
            elif isinstance(node.func.value, ast.Attribute):
                # Handle chained: Gui.ActiveDocument.getObject
                inner = self._get_call_string(
                    ast.Call(func=node.func.value, args=[], keywords=[])
                )
                if inner:
                    return f"{inner}.{node.func.attr}"
        elif isinstance(node.func, ast.Name):
            return node.func.id
        return None
    
    def _check_document_creation(self, script: str) -> bool:
        """Check if the script creates a FreeCAD document."""
        doc_patterns = [
            r'App\.newDocument',
            r'FreeCAD\.newDocument',
            r'newDocument\s*\(',
            r'App\.openDocument',
            r'FreeCAD\.openDocument',
        ]
        for pattern in doc_patterns:
            if re.search(pattern, script):
                return True
        return False
    
    def _estimate_complexity(self, script: str) -> dict:
        """
        Estimate script complexity for dynamic timeout allocation.
        
        Factors:
        - Line count (effective, non-blank/comment)
        - Loop depth (nested for/while loops)
        - Boolean operation count (fuse/cut/common)
        - Array/pattern operations
        - Number of Part.make* calls
        """
        effective_lines = self._count_effective_lines(script)
        
        # Count complexity indicators
        loop_count = len(re.findall(r'\bfor\b|\bwhile\b', script))
        boolean_ops = len(re.findall(r'\.(fuse|cut|common|multiFuse|multiCommon)\s*\(', script))
        make_calls = len(re.findall(r'Part\.make\w+\s*\(', script))
        array_ops = len(re.findall(r'Draft\.make.*[Aa]rray|Draft\.array|Draft\.polar', script))
        loft_sweep = len(re.findall(r'Part\.make(Loft|Sweep|Shell|Solid|Compound)\s*\(', script))
        
        # Weighted complexity score
        complexity_score = (
            effective_lines * 1.0 +
            loop_count * 15 +
            boolean_ops * 10 +
            make_calls * 3 +
            array_ops * 20 +
            loft_sweep * 15
        )
        
        warnings = []
        
        if complexity_score < 150:
            level = "simple"
            timeout = 60
        elif complexity_score < 500:
            level = "medium"
            timeout = 180
        else:
            level = "complex"
            timeout = 600
            if boolean_ops > 20:
                warnings.append(
                    f"High boolean operation count ({boolean_ops}). "
                    "Script may be slow or crash FreeCAD."
                )
            if loop_count > 10:
                warnings.append(
                    f"High loop count ({loop_count}). "
                    "Consider using Draft.array for repetitive geometry."
                )
        
        return {
            "level": level,
            "timeout": timeout,
            "score": complexity_score,
            "breakdown": {
                "effective_lines": effective_lines,
                "loops": loop_count,
                "boolean_ops": boolean_ops,
                "make_calls": make_calls,
                "array_ops": array_ops,
                "loft_sweep": loft_sweep,
            },
            "warnings": warnings,
        }
    
    def _classify_complexity_from_lines(self, line_count: int) -> str:
        """Fallback complexity classification when AST is unavailable."""
        if line_count < 80:
            return "simple"
        elif line_count < 300:
            return "medium"
        return "complex"
    
    def _estimate_timeout_from_lines(self, line_count: int) -> int:
        """Fallback timeout estimation when AST is unavailable."""
        if line_count < 80:
            return 60
        elif line_count < 300:
            return 180
        return 600
