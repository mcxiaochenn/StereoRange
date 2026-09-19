import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

const repositoryUrl = 'https://github.com/mcxiaochenn/StereoRange';

/// 使用系统浏览器查看仓库，不在应用内加载网页。
class RepositoryCard extends StatelessWidget {
  const RepositoryCard({super.key});
  @override
  Widget build(BuildContext context) => Card.filled(
    clipBehavior: Clip.antiAlias,
    child: ListTile(
      leading: const Icon(Icons.code_rounded),
      title: const Text('GitHub 项目仓库'),
      subtitle: const Text(repositoryUrl),
      trailing: const Icon(Icons.open_in_new),
      onTap: () async {
        try {
          await const MethodChannel('stereorange/android')
              .invokeMethod<void>('openRepository');
        } on PlatformException catch (error) {
          if (!context.mounted) return;
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(error.message ?? '无法打开浏览器，请检查是否已安装浏览器')),
          );
        }
      },
    ),
  );
}
