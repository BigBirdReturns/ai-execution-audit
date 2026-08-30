from __future__ import annotations

from pathlib import Path

path = Path("mating_surface/anchor_node/conformance/test_stc_mary_flight_01_cartridge.py")
text = path.read_text(encoding="utf-8")

root_old = '''        symlink_root = self.parent / "cartridge-root-symlink"
        try:
            symlink_root.symlink_to(self.root, target_is_directory=True)
        except OSError as exc:
            if os.name == "nt":
                self.skipTest(f"Windows runner cannot create directory symlink: {exc}")
            raise
'''
root_new = '''        symlink_root = self.parent / "cartridge-root-symlink"
        make_directory_link(symlink_root, self.root)
        self.addCleanup(remove_directory_link, symlink_root)
'''
if text.count(root_old) != 1:
    raise SystemExit(f"root link witness anchor differs: {text.count(root_old)}")
text = text.replace(root_old, root_new, 1)

ancestor_old = '''        ancestor_link = self.parent / "cartridge-parent-symlink"
        ancestor_link.symlink_to(self.root.parent, target_is_directory=True)
        nested_symlink_root = ancestor_link / self.root.name
'''
ancestor_new = '''        ancestor_link = self.parent / "cartridge-parent-symlink"
        make_directory_link(ancestor_link, self.root.parent)
        self.addCleanup(remove_directory_link, ancestor_link)
        nested_symlink_root = ancestor_link / self.root.name
'''
if text.count(ancestor_old) != 1:
    raise SystemExit(f"ancestor link witness anchor differs: {text.count(ancestor_old)}")
text = text.replace(ancestor_old, ancestor_new, 1)

if "self.skipTest(" in text:
    raise SystemExit("junction custody witness still contains a skipTest escape")

path.write_text(text, encoding="utf-8", newline="\n")
