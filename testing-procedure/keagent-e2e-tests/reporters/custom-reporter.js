// reporters/custom-reporter.js
class CustomNestedReporter {
  onBegin(config, suite) {
    const rootTitle = suite.suites[0]?.title || 'SaaS Automation Suite';
    console.log('\n==================================================');
    console.log(`TEST SUITE: ${rootTitle}`);
    console.log('==================================================\n');
  }

  onTestEnd(test, result) {
    // Extract test number from title (e.g. "1.1" from "1.1 Action: Navigate...")
    const match = test.title.match(/^(\d+(\.\d+)*)/);
    const testId = match ? match[1] : 'Test';
    const status = result.status === 'passed' ? 'Passed' : 'Failed';

    console.log(`Test ${testId} ${status}`);

    if (result.status === 'failed' && result.error) {
      console.log(`   └─ Error: ${result.error.message?.split('\n')[0]}`);
    }
  }

  onEnd(result) {
    console.log('\n==================================================');
    console.log(`Suite Execution Completed: ${result.status.toUpperCase()}`);
    console.log('==================================================\n');
  }
}

module.exports = CustomNestedReporter;