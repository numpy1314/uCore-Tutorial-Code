"""Install course tools into an explicitly selected Git checkout."""

import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

RUNTIME_PATH = Path('.ai/course-tools')
HOOKS_PATH = '.ai/course-tools/.course-monitor/hooks'
LOCAL_PATHS = (
    '.ai/course-tools/', '.ai/ide/',
    '.codex/config.toml', '.codex/session-archive.json',
    '.claude/settings.json', '.claude/settings.local.json', '.claude/session-archive.json',
    '.cursor/hooks.json', '.cursor/session-archive.json', '.cursor/ucore-hooks/',
    '.vscode/session-archive.json', '.vscode/ucore-hooks/',
    '.opencode/session-archive.json', '.opencode/ucore-hooks/',
    '.opencode/plugins/ucore-session-archive.js',
    '.github/hooks/ucore-session-archive.json',
)
BUNDLE_FILES = ('course.py', '.course-monitor', 'plugins/ucore-session-archive',
                'scripts', '.agents/plugins/marketplace.json', '.claude-plugin/marketplace.json')


def project_root(bundle):
    bundle = Path(bundle).resolve()
    if bundle.name == 'course-tools' and bundle.parent.name == '.ai':
        return bundle.parent.parent
    return bundle


def resolve_project(bundle, project=None):
    """Preserve bundled installs; allow an explicit external project or caller checkout."""
    bundle = Path(bundle).resolve()
    if project is None:
        owner = project_root(bundle)
        if owner != bundle:
            return owner
        # Course repositories distribute this entry on main. Keep their existing
        # no-argument install working even when invoked outside the checkout.
        source = subprocess.run(['git', '-C', str(bundle), 'rev-parse', '--show-toplevel'],
                                text=True, encoding='utf-8', capture_output=True)
        if source.returncode == 0 and Path(source.stdout.strip()).resolve() == bundle:
            return bundle
    location = Path(project).expanduser().resolve() if project is not None else Path.cwd()
    result = subprocess.run(['git', '-C', str(location), 'rev-parse', '--show-toplevel'],
                            text=True, encoding='utf-8', capture_output=True)
    if result.returncode:
        raise ValueError('请用 --project 指定已有的 Git 项目目录。')
    return Path(result.stdout.strip()).resolve()


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True, encoding='utf-8').strip()


def ordinary_path(root, path):
    for candidate in (path, *path.parents):
        if candidate == root:
            break
        if candidate.is_symlink():
            raise ValueError('记录工具路径不能是符号链接：' + str(candidate))


def write_file(path, content, mode=0o600):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(descriptor, 'wb') as output:
            output.write(content)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def record_ignore_updates(root):
    """Prepare branch-local record rules while preserving existing ignore entries."""
    files = [(root / '.gitignore', '/.ai/')]
    nested = root / '.ai/.gitignore'
    if nested.exists() or nested.is_symlink():
        files.append((nested, ''))
    updates = []
    for path, prefix in files:
        ordinary_path(root, path)
        lines = ['# >>> course-tool records']
        if prefix:
            lines += ['!/.ai/', '!/.ai/.gitignore']
        for name in ('agent-sessions', 'events', 'submissions'):
            lines += ['!' + prefix + name + '/', '!' + prefix + name + '/**']
        lines += ['# <<< course-tool records']
        block = '\n'.join(lines) + '\n'
        current = path.read_text(encoding='utf-8') if path.exists() else ''
        base = current.replace(block, '').rstrip('\n')
        text = (base + '\n\n' if base else '') + block
        if text != current:
            updates.append((path, text.encode('utf-8'), path.stat().st_mode & 0o777 if path.exists() else 0o644))
    return updates


def install_runtime(bundle, root=None):
    """Copy only executable tooling; preserve the installed project policy."""
    bundle = Path(bundle).resolve()
    root = resolve_project(bundle) if root is None else Path(root).resolve()
    if Path(git(root, 'rev-parse', '--show-toplevel')).resolve() != root:
        raise ValueError('请在实验仓库根目录安装记录工具。')
    runtime = root / RUNTIME_PATH
    ordinary_path(root, runtime)
    ignore_updates = record_ignore_updates(root)
    if bundle != runtime:
        copies = []
        for name in BUNDLE_FILES:
            source = bundle / name
            if not source.exists():
                raise ValueError('记录工具文件缺失，请从完整的 course-tool 仓库安装：' + name)
            for path in sorted(source.rglob('*')) if source.is_dir() else [source]:
                if path.is_symlink():
                    raise ValueError('记录工具源文件不能是符号链接：' + str(path))
                if not path.is_file() or '__pycache__' in path.parts or path.suffix in {'.pyc', '.pyo'} or path.is_relative_to(bundle / '.course-monitor/node'):
                    continue
                relative = path.relative_to(bundle)
                destination = runtime / relative
                ordinary_path(root, destination)
                if relative.as_posix() == '.course-monitor/config.json' and destination.exists():
                    continue
                copies.append((path, destination))
        for source, destination in copies:
            write_file(destination, source.read_bytes(), 0o700 if source.stat().st_mode & 0o111 else 0o600)
    if not (runtime / 'plugins/ucore-session-archive/scripts/setup_agents.py').is_file():
        raise ValueError('归档插件运行文件不完整，请从 course-tool 仓库重新安装。')
    exclude = Path(git(root, 'rev-parse', '--git-path', 'info/exclude'))
    if not exclude.is_absolute():
        exclude = root / exclude
    if exclude.is_symlink():
        raise ValueError('Git 本地排除配置不能是符号链接。')
    current = exclude.read_text(encoding='utf-8') if exclude.exists() else ''
    # Migrate older installs so existing course records can be submitted with code.
    record_patterns = {'/.ai/' + name + '/' for name in ('agent-sessions', 'events', 'submissions')}
    text = ''.join(line for line in current.splitlines(keepends=True)
                   if line.rstrip('\r\n') not in record_patterns)
    # Source-side caches remain after main's tracked Python files are checked out.
    # Keep these patterns unanchored so they cover caches at any directory depth.
    patterns = ['/' + name for name in LOCAL_PATHS] + ['__pycache__/', '*.py[cod]']
    missing = [pattern for pattern in patterns if pattern not in text.splitlines()]
    if missing:
        text += '\n' if text and not text.endswith('\n') else ''
        text += '# Installed course tools and local configuration survive branch switches.\n'
        text += '\n'.join(missing) + '\n'
    if text != current:
        write_file(exclude, text.encode('utf-8'))
    for path, content, mode in ignore_updates:
        write_file(path, content, mode)
    aliases = {
        'course': [sys.executable, str(RUNTIME_PATH / 'course.py')],
        'agent-plugins': [sys.executable, str(RUNTIME_PATH / 'plugins/ucore-session-archive/scripts/setup_agents.py')],
    }
    for name, command in aliases.items():
        git(root, 'config', '--local', 'alias.' + name, '!' + shlex.join(command))
    return runtime
