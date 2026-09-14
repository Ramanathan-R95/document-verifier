const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

const projectRoot = path.resolve(__dirname, '../../../');
const aiRoot = path.join(projectRoot, 'ai');
const SERVICE_NAMES = new Set(['ocr', 'validation', 'tampering', 'face', 'risk_calculator']);
// Increased to 120s (120000ms) to account for Python startup, module imports, and Tesseract initialization
const DEFAULT_TIMEOUT_MS = 120 * 1000;

const findPythonExecutable = () => {
  const candidates = [];

  if (process.env.PYTHON_PATH) candidates.push(process.env.PYTHON_PATH);

  candidates.push(
    path.join(aiRoot, '.venv', 'bin', 'python3'),
    path.join(aiRoot, '.venv', 'bin', 'python'),
    path.join(aiRoot, 'venv', 'bin', 'python3'),
    path.join(aiRoot, 'venv', 'bin', 'python')
  );

  candidates.push('/usr/local/bin/python3', '/usr/local/bin/python');
  candidates.push('/usr/bin/python3', '/usr/bin/python');
  candidates.push('python3', 'python');

  for (const candidate of candidates) {
    if (!candidate) continue;

    if (path.isAbsolute(candidate)) {
      if (fs.existsSync(candidate)) return candidate;
      continue;
    }

    // Keep the executable name if it exists on PATH.
    return candidate;
  }

  return 'python3';
};

/**
 * Call a Python service and return JSON results
 * @param {string} serviceName - Name of the Python service (e.g., 'ocr', 'tampering')
 * @param {object} data - Input data
 * @returns {Promise<object>} - Python service output
 */
const callPythonService = async (serviceName, data) => {
  return new Promise((resolve, reject) => {
    if (!SERVICE_NAMES.has(serviceName)) {
      reject(new Error(`Unsupported Python service: ${serviceName}`));
      return;
    }

    const pythonScriptPath = path.join(aiRoot, 'services', `${serviceName}_service.py`);
    const pythonExec = findPythonExecutable();
    const timeoutMs = Number(process.env.AI_SERVICE_TIMEOUT_MS) || DEFAULT_TIMEOUT_MS;

    const pythonProcess = spawn(pythonExec, [pythonScriptPath], {
      cwd: aiRoot,
    });

    let settled = false;
    const finish = (callback) => {
      if (settled) return;
      settled = true;
      clearTimeout(timeout);
      callback();
    };

    const timeout = setTimeout(() => {
      pythonProcess.kill('SIGKILL');
      finish(() => reject(new Error(`Python ${serviceName} service timed out after ${timeoutMs}ms`)));
    }, timeoutMs);

    // Handle spawn errors (e.g., ENOENT) to avoid unhandled 'error' events crashing Node
    pythonProcess.on('error', (err) => {
      finish(() => reject(new Error(`Failed to start Python process (${pythonExec}): ${err.message}`)));
    });

    let output = '';
    let errorOutput = '';

    pythonProcess.stdout.on('data', (data) => {
      output += data.toString();
    });

    pythonProcess.stderr.on('data', (data) => {
      errorOutput += data.toString();
    });

    pythonProcess.on('close', (code) => {
      if (code !== 0) {
        finish(() => reject(new Error(`Python ${serviceName} service failed (exit ${code}): ${errorOutput.trim() || 'unknown error'}`)));
        return;
      }

      try {
        const result = JSON.parse(output);
        if (!result || typeof result !== 'object' || Array.isArray(result)) {
          throw new Error('response must be a JSON object');
        }
        finish(() => resolve(result));
      } catch (error) {
        finish(() => reject(new Error(`Invalid response from Python ${serviceName} service: ${error.message}`)));
      }
    });

    // Send data to Python process via stdin
    pythonProcess.stdin.write(JSON.stringify(data));
    pythonProcess.stdin.end();
  });
};

module.exports = {
  callPythonService,
};
