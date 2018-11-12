# external
import tomlkit

# app
from ..models import Constraint, Dependency, RootDependency
from ..repositories import get_repo
from .base import BaseConverter


VCS_LIST = ('git', 'svn', 'hg', 'bzr')


class PIPFileConverter(BaseConverter):
    lock = False
    fields = (
        'version', 'editable', 'extras', 'markers',
        'ref', 'vcs', 'index', 'hashes',
        'subdirectory', 'path', 'file', 'uri',
        'git', 'svn', 'hg', 'bzr',
    )

    def loads(self, content) -> RootDependency:
        doc = tomlkit.parse(content)
        deps = []
        root = RootDependency(self._get_name(content=content))
        if 'packages' in doc:
            for name, content in doc['packages'].items():
                deps.append(self._make_dep(root, name, content))
        root.attach_dependencies(deps)
        return root

    def dumps(self, reqs, content=None) -> str:
        if content:
            doc = tomlkit.parse(content)
        else:
            doc = tomlkit.document()

        if 'source' not in doc:
            source = tomlkit.table()
            source['url'] = 'https://pypi.python.org/simple'
            source['verify_ssl'] = True
            source['name'] = 'pypi'
            sources = tomlkit.aot()
            sources.append(source)
            doc.add('source', sources)

        if 'packages' in doc:
            # clean packages from old packages
            names = {req.name for req in reqs}
            doc['packages'] = {
                name: info
                for name, info in doc['packages'].items()
                if name in names
            }
            # write new packages to this table
            packages = doc['packages']
        else:
            packages = tomlkit.table()

        for req in reqs:
            packages[req.name] = self._format_req(req=req)
        doc['packages'] = packages

        return tomlkit.dumps(doc)

    # https://github.com/pypa/pipfile/blob/master/examples/Pipfile
    @staticmethod
    def _make_dep(root, name: str, content) -> Dependency:
        if isinstance(content, str):
            return Dependency(
                raw_name=name,
                constraint=Constraint(root, content),
                repo=get_repo(),
            )

        # get link
        url = content.get('file') or content.get('path') or content.get('vcs')
        if not url:
            for vcs in VCS_LIST:
                if vcs in content:
                    url = vcs + '+' + content[vcs]
                    break
        if 'ref' in content:
            url += '@' + content['ref']

        # https://github.com/sarugaku/requirementslib/blob/master/src/requirementslib/models/requirements.py
        # https://github.com/pypa/pipenv/blob/master/pipenv/project.py
        return Dependency.from_params(
            raw_name=name,
            # https://github.com/sarugaku/requirementslib/blob/master/src/requirementslib/models/utils.py
            constraint=Constraint(root, content.get('version', '')),
            extras=set(content.get('extras', [])),
            marker=content.get('markers'),
            url=url,
        )

    def _format_req(self, req, *, short=True):
        result = tomlkit.inline_table()
        for name, value in req:
            if name in self.fields:
                if isinstance(value, tuple):
                    value = list(value)
                result[name] = value
        if 'version' not in result:
            result['version'] = '*'
        # if we have only version, return string instead of table
        if short and tuple(result.value) == ('version', ):
            return result['version']
        # do not specify version explicit
        if result['version'] == '*':
            del result['version']

        return result
