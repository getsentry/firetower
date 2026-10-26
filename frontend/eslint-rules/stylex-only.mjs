export default {
  meta: {
    type: 'problem',
    schema: [],
    messages: {
      className:
        'Define styles with StyleX and pass a typed style prop or spread stylex.props on a host element.',
      inlineStyle:
        'Define host styles with stylex.create and apply them with stylex.props.',
      cssProperties: 'Component style props must accept StyleXStyles, not CSSProperties.',
      hostProps:
        'Pass StyleX styles to application components instead of spreading generated DOM props.',
    },
  },
  create(context) {
    function applicationComponent(node) {
      const name = node.type === 'JSXMemberExpression' ? node.object : node;
      if (name.type !== 'JSXIdentifier' || !/^[A-Z]/.test(name.name)) return false;
      let scope = context.sourceCode.getScope(node);
      while (scope && !scope.set.has(name.name)) scope = scope.upper;
      const variable = scope?.set.get(name.name);
      const imported = variable?.defs.find(def => def.type === 'ImportBinding');
      if (!imported) {
        return Boolean(
          variable?.defs.some(
            def =>
              def.type === 'FunctionName' ||
              (def.type === 'Variable' &&
                ['ArrowFunctionExpression', 'FunctionExpression'].includes(
                  def.node.init?.type
                ))
          )
        );
      }
      const source = imported.parent.source.value;
      return (
        source.startsWith('components/') ||
        source.startsWith('./') ||
        source.startsWith('../')
      );
    }

    function initializer(node) {
      if (node.type !== 'Identifier') return node;
      let scope = context.sourceCode.getScope(node);
      while (scope && !scope.set.has(node.name)) scope = scope.upper;
      return scope?.set.get(node.name)?.defs.find(def => def.type === 'Variable')?.node
        .init;
    }

    function spreadValues(node, seen = new Set()) {
      if (!node || seen.has(node)) return [];
      seen.add(node);
      if (
        node.type === 'TSAsExpression' ||
        node.type === 'TSSatisfiesExpression' ||
        node.type === 'TSNonNullExpression'
      ) {
        return spreadValues(node.expression, seen);
      }
      if (node.type === 'Identifier') return spreadValues(initializer(node), seen);
      if (node.type === 'ObjectExpression') {
        return node.properties.flatMap(property =>
          property.type === 'SpreadElement'
            ? spreadValues(property.argument, seen)
            : [property]
        );
      }
      if (
        node.type === 'CallExpression' &&
        node.callee.type === 'MemberExpression' &&
        node.callee.object.name === 'stylex' &&
        node.callee.property.name === 'props'
      ) {
        return [node];
      }
      return [];
    }

    return {
      JSXAttribute(node) {
        if (node.name.name === 'className')
          context.report({node, messageId: 'className'});
        if (
          node.name.name === 'classNames' &&
          !context.filename.endsWith('/components/Calendar.tsx')
        ) {
          context.report({node, messageId: 'className'});
        }
        if (
          node.name.name === 'style' &&
          (!applicationComponent(node.parent.name) ||
            node.value?.expression?.type === 'ObjectExpression')
        ) {
          context.report({node, messageId: 'inlineStyle'});
        }
      },
      TSTypeReference(node) {
        const name =
          node.typeName.type === 'TSQualifiedName'
            ? node.typeName.right.name
            : node.typeName.name;
        if (name === 'CSSProperties') context.report({node, messageId: 'cssProperties'});
      },
      AssignmentExpression(node) {
        if (
          node.left.type === 'MemberExpression' &&
          node.left.object.type === 'MemberExpression' &&
          node.left.object.property.name === 'style'
        ) {
          context.report({node, messageId: 'inlineStyle'});
        }
      },
      JSXSpreadAttribute(node) {
        const host = node.parent.name;
        const values = spreadValues(node.argument);
        for (const value of values) {
          if (value.type !== 'Property' || value.computed) continue;
          const key = value.key.name ?? value.key.value;
          if (key === 'className' || key === 'classNames') {
            context.report({node: value, messageId: 'className'});
          }
          if (
            key === 'style' &&
            (!applicationComponent(host) || value.value.type === 'ObjectExpression')
          ) {
            context.report({node: value, messageId: 'inlineStyle'});
          }
        }
        if (!values.some(value => value.type === 'CallExpression')) return;
        if (applicationComponent(host)) {
          context.report({node, messageId: 'hostProps'});
        }
      },
    };
  },
};
